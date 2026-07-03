"""
Seam-free DETECTOR -> SAM segmentation of any drone ortho.
Usage: python run_detector_sam.py <ortho> <out.gpkg>

Pipeline (overlapping tiles + dedup, like segment_2025_overlap.py, but proposals
come from the trained YOLO feature detector instead of blind AMG):
  1. Reproject the 2026 ortho (EPSG:4326) to UTM 32N on the fly via WarpedVRT.
  2. Overlapping 1024px tiles (stride 768 ~1 m overlap).
  3. Per tile: YOLO detector -> boxes; DROP boxes touching an interior tile seam
     (caught whole in the neighbour); skip tile if no boxes.
  4. Each kept box -> fine-tuned SAM decoder -> mask -> polygon (score = det conf).
  5. Checkpoint raw polygons, then IoU/containment dedup of overlap duplicates.
Output: SAM_prototype/sam_architecture_2026_detector.gpkg (EPSG:32632)

GPU required. Run only when the GPU is free.
"""
import os, time
import numpy as np
import torch
import rasterio
from rasterio.vrt import WarpedVRT
from rasterio.enums import Resampling
from rasterio.windows import Window
from rasterio.features import shapes
import geopandas as gpd
from shapely.geometry import shape
from shapely.strtree import STRtree
from shapely.validation import make_valid
from segment_anything import sam_model_registry
from segment_anything.utils.transforms import ResizeLongestSide
from ultralytics import YOLO

SP = os.path.dirname(os.path.abspath(__file__))
REPO = r"C:\Users\Photogrammetry\AutomateSuSheetCreation"
import sys
ORTHO_SRC = sys.argv[1]
CKPT = os.path.expanduser(r"~/.cache/torch/hub/checkpoints/sam_vit_h_4b8939.pth")
FT = os.path.join(SP, "sam_decoder_multiyear.pth")
DET = os.path.join(SP, "yolo_runs", "feature_detector", "weights", "best.pt")
OUT = sys.argv[2]
RAW_OUT = OUT.replace(".gpkg", "_raw.gpkg")
DEV = "cuda"; TILE = 1024; STRIDE = 768; MARGIN = 3; CONF = 0.25
DST_CRS = "EPSG:32632"

def log(*a): print(*a, flush=True)

t0 = time.time()
log("loading SAM vit_h + fine-tuned decoder + YOLO detector ...")
sam = sam_model_registry["vit_h"](checkpoint=CKPT).to(DEV)
sam.mask_decoder.load_state_dict(torch.load(FT, map_location=DEV))
sam.eval()
tf = ResizeLongestSide(sam.image_encoder.img_size)
img_pe = sam.prompt_encoder.get_dense_pe()
det = YOLO(DET)

def predict_masks(emb_gpu, boxes_np):
    bx = tf.apply_boxes(boxes_np, (TILE, TILE))
    bx = torch.as_tensor(bx, dtype=torch.float, device=DEV)
    with torch.no_grad():
        sp_, de_ = sam.prompt_encoder(points=None, boxes=bx, masks=None)
        lr, _ = sam.mask_decoder(image_embeddings=emb_gpu, image_pe=img_pe,
                                 sparse_prompt_embeddings=sp_, dense_prompt_embeddings=de_,
                                 multimask_output=False)
        hr = sam.postprocess_masks(lr, (TILE, TILE), (TILE, TILE))
    return hr[:, 0]

def offsets(total):
    o = list(range(0, total - TILE + 1, STRIDE))
    if not o or o[-1] != total - TILE:
        o.append(total - TILE)
    return sorted(set(o))

# ---------- Phase 1: detect + segment (checkpointed) ----------
if os.path.exists(RAW_OUT):
    log(f"loading cached raw polygons from {RAW_OUT} ...")
    rawg = gpd.read_file(RAW_OUT)
    geoms = list(rawg.geometry.values)
    scores = list(rawg["score"].values) if "score" in rawg.columns else [1.0] * len(geoms)
else:
    src0 = rasterio.open(ORTHO_SRC)
    vrt = WarpedVRT(src0, crs=DST_CRS, resampling=Resampling.bilinear)
    W, H = vrt.width, vrt.height
    px = abs(vrt.transform.a); TILE_AREA = (TILE * px) ** 2
    cols, rows = offsets(W), offsets(H)
    ntiles = len(cols) * len(rows)
    log(f"2026 ortho warped to {DST_CRS}: {W}x{H}, px~{px*1000:.1f} mm, "
        f"tile~{TILE*px:.1f} m -> {len(cols)}x{len(rows)}={ntiles} tiles (overlap {(TILE-STRIDE)*px:.2f} m)")
    geoms, scores = [], []
    done = 0; ndet = 0
    nbands = vrt.count
    for tj in rows:
        for ti in cols:
            win = Window(ti, tj, TILE, TILE); wt = vrt.window_transform(win)
            arr = vrt.read(indexes=[1, 2, 3] if nbands >= 3 else [1, 1, 1], window=win)
            img = np.transpose(arr, (1, 2, 0)).astype("uint8")   # HWC RGB
            done += 1
            if img.mean() < 3: continue
            # YOLO expects BGR numpy
            res = det.predict(img[:, :, ::-1], conf=CONF, imgsz=1024, device=0,
                              max_det=1000, verbose=False)[0]
            if len(res.boxes) == 0: continue
            xyxy = res.boxes.xyxy.cpu().numpy()
            conf = res.boxes.conf.cpu().numpy()
            keep_boxes, keep_conf = [], []
            for (x0, y0, x1, y1), c in zip(xyxy, conf):
                if (x0 <= MARGIN and ti > 0): continue
                if (x1 >= TILE - MARGIN and ti + TILE < W): continue
                if (y0 <= MARGIN and tj > 0): continue
                if (y1 >= TILE - MARGIN and tj + TILE < H): continue
                keep_boxes.append([x0, y0, x1, y1]); keep_conf.append(float(c))
            if not keep_boxes: continue
            ndet += len(keep_boxes)
            inp = tf.apply_image(img)
            t = torch.as_tensor(inp, device=DEV).permute(2, 0, 1).contiguous()[None]
            t = sam.preprocess(t)
            with torch.no_grad():
                emb = sam.image_encoder(t)
            boxes_np = np.array(keep_boxes, dtype=np.float32)
            for s in range(0, len(boxes_np), 64):
                logits = predict_masks(emb, boxes_np[s:s+64])
                masks = (logits > 0).cpu().numpy().astype("uint8")
                for k, m in enumerate(masks):
                    best = None; barea = 0
                    for g, v in shapes(m, mask=m.astype(bool), transform=wt):
                        p = shape(g)
                        if p.area > barea: best, barea = p, p.area
                    if best is None or barea < 0.004 or barea > 0.5 * TILE_AREA:
                        continue
                    geoms.append(best.simplify(0.003))
                    scores.append(keep_conf[s + k])
            if done % 25 == 0:
                log(f"  {done}/{ntiles} tiles, {ndet} dets, {len(geoms)} polys, {time.time()-t0:.0f}s")
    gpd.GeoDataFrame({"id": range(len(geoms)), "score": scores},
                     geometry=geoms, crs=DST_CRS).to_file(RAW_OUT, driver="GPKG")
    log(f"raw polygons: {len(geoms)} -> saved {RAW_OUT}  ({time.time()-t0:.0f}s)")

# ---------- Phase 2: validate + dedup ----------
log("validating geometries ...")
fixed = []
for g in geoms:
    try:
        if g is None or g.is_empty: fixed.append(None); continue
        fixed.append(g if g.is_valid else make_valid(g))
    except Exception:
        fixed.append(None)
geoms = fixed
scores = np.asarray(scores, dtype=float)
areas = np.array([g.area if g is not None else 0.0 for g in geoms])
valid_idx = [i for i, g in enumerate(geoms) if g is not None and areas[i] > 0]
log(f"dedup over {len(valid_idx)} polygons ...")
tree = STRtree([geoms[i] for i in valid_idx])
parent = list(range(len(geoms)))
def find(a):
    while parent[a] != a:
        parent[a] = parent[parent[a]]; a = parent[a]
    return a
def union(a, b):
    ra, rb = find(a), find(b)
    if ra != rb: parent[ra] = rb
for i in valid_idx:
    g = geoms[i]
    for q in tree.query(g):
        j = valid_idx[q]
        if j <= i: continue
        gj = geoms[j]
        try:
            if not g.intersects(gj): continue
            inter = g.intersection(gj).area
        except Exception:
            continue
        if inter <= 0: continue
        iou = inter / (areas[i] + areas[j] - inter)
        ios = inter / min(areas[i], areas[j])
        if iou > 0.5 or ios > 0.7:
            union(i, j)
groups = {}
for i in valid_idx:
    groups.setdefault(find(i), []).append(i)
keep = [max(members, key=lambda k: (scores[k], areas[k])) for members in groups.values()]
log(f"dedup: {len(valid_idx)} -> {len(keep)} polygons")

gpd.GeoDataFrame({"id": range(len(keep)), "score": scores[keep]},
                 geometry=[geoms[k] for k in keep], crs=DST_CRS).to_file(OUT, driver="GPKG")
log(f"wrote {OUT}  ({time.time()-t0:.0f}s)")
log("DONE")
