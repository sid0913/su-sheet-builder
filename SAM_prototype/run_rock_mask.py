"""
Unified rock-mask runner — ONE script, THREE toggleable models.

    python run_rock_mask.py --model MODEL <ortho.tif> <out.gpkg> [--dem DEM.tif]

    MODEL = yolo_sam     YOLO feature-detector boxes -> fine-tuned SAM (box-prompted).
                         Rocks/stones ONLY, ~human polygon count. RECOMMENDED layer.
            rgb_sam      Fine-tuned SAM automatic mask generator on RGB.
                         Segments EVERYTHING (stones + ground/veg), over-segments.
            rgb_dem_sam  Like rgb_sam but the input is RGB blended 50/50 with a
                         hillshade computed from a co-registered DEM (--dem REQUIRED).
                         The "DEM-fusion" model. Only valid where the DEM covers.

All three share: ViT-H + the SAME fine-tuned multi-year decoder
(sam_decoder_multiyear.pth), on-the-fly reprojection to UTM 32N (WarpedVRT),
overlapping 1024px tiles (stride 768) with interior-seam dropping, a raw-polygon
checkpoint, and IoU/containment dedup. They differ ONLY in how stones are proposed
(detector boxes vs. automatic point grid) and in the input channels (RGB vs RGB+height).

Provenance / why rgb_dem_sam exists: the worktree-dem-fusion experiment asked whether
fusing DEM height into SAM beats plain RGB. Verdict: it does NOT (box-prompted IoU
RGB 0.62 vs fused 0.63 = noise; automatic recall RGB 0.22 vs fused 0.18 = RGB wins).
rgb_dem_sam is kept as a selectable option, not because it is better.

GPU required. Run only when the GPU is free (shared with Metashape/MeshLab).
"""
import os, sys, time, argparse
import numpy as np
import torch
import rasterio
from rasterio.vrt import WarpedVRT
from rasterio.enums import Resampling
from rasterio.windows import Window, from_bounds, bounds as win_bounds
from rasterio.features import shapes
import geopandas as gpd
from shapely.geometry import shape
from shapely.strtree import STRtree
from shapely.validation import make_valid
from segment_anything import sam_model_registry, SamAutomaticMaskGenerator
from segment_anything.utils.transforms import ResizeLongestSide

SP = os.path.dirname(os.path.abspath(__file__))
CKPT = os.path.expanduser(r"~/.cache/torch/hub/checkpoints/sam_vit_h_4b8939.pth")
FT = os.path.join(SP, "sam_decoder_multiyear.pth")
DET = os.path.join(SP, "yolo_runs", "feature_detector", "weights", "best.pt")
DEV = "cuda"; TILE = 1024; STRIDE = 768; MARGIN = 3; DST_CRS = "EPSG:32632"
CONF = 0.25                       # yolo_sam: detector confidence
AMG_KW = dict(points_per_side=48, pred_iou_thresh=0.80, stability_score_thresh=0.88,
              crop_n_layers=0, min_mask_region_area=120)   # rgb_sam / rgb_dem_sam

ap = argparse.ArgumentParser()
ap.add_argument("--model", required=True, choices=["yolo_sam", "rgb_sam", "rgb_dem_sam"])
ap.add_argument("ortho"); ap.add_argument("out")
ap.add_argument("--dem", default=None, help="co-registered DEM (required for rgb_dem_sam)")
ap.add_argument("--max-tiles", type=int, default=0, help="smoke test: cap tiles processed (0=all)")
A = ap.parse_args()
if A.model == "rgb_dem_sam" and not A.dem:
    sys.exit("rgb_dem_sam requires --dem <DEM.tif>")
OUT = A.out; RAW_OUT = OUT.replace(".gpkg", "_raw.gpkg")

def log(*a): print(*a, flush=True)
t0 = time.time()

# ---------- models ----------
log(f"[{A.model}] loading SAM vit_h + fine-tuned multi-year decoder ...")
sam = sam_model_registry["vit_h"](checkpoint=CKPT).to(DEV)
sam.mask_decoder.load_state_dict(torch.load(FT, map_location=DEV))
sam.eval()
tf = ResizeLongestSide(sam.image_encoder.img_size)
img_pe = sam.prompt_encoder.get_dense_pe()
det = amg = None
if A.model == "yolo_sam":
    from ultralytics import YOLO
    det = YOLO(DET)
else:
    amg = SamAutomaticMaskGenerator(sam, **AMG_KW)

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

def hillshade(dem, cell, az=315.0, alt=45.0):
    """Standard Horn hillshade -> uint8 0..255. dem in metres, cell = px size (m)."""
    az = np.radians(360.0 - az + 90.0); alt = np.radians(alt)
    dy, dx = np.gradient(dem.astype("float32"), cell)
    slope = np.pi / 2.0 - np.arctan(np.hypot(dx, dy))
    aspect = np.arctan2(-dx, dy)
    sh = np.sin(alt) * np.sin(slope) + np.cos(alt) * np.cos(slope) * np.cos(az - aspect)
    return np.clip(sh * 255.0, 0, 255).astype("uint8")

def offsets(total):
    o = list(range(0, total - TILE + 1, STRIDE))
    if not o or o[-1] != total - TILE: o.append(total - TILE)
    return sorted(set(o))

def biggest_poly(mask_u8, wt):
    best, ba = None, 0.0
    for g, v in shapes(mask_u8, mask=mask_u8.astype(bool), transform=wt):
        p = shape(g)
        if p.area > ba: best, ba = p, p.area
    return best, ba

# ---------- Phase 1: propose + segment (checkpointed) ----------
if os.path.exists(RAW_OUT):
    log(f"loading cached raw polygons from {RAW_OUT} ...")
    rawg = gpd.read_file(RAW_OUT); geoms = list(rawg.geometry.values)
    scores = list(rawg["score"].values) if "score" in rawg.columns else [1.0] * len(geoms)
else:
    src0 = rasterio.open(A.ortho)
    vrt = WarpedVRT(src0, crs=DST_CRS, resampling=Resampling.bilinear)
    W, H = vrt.width, vrt.height
    px = abs(vrt.transform.a); TILE_AREA = (TILE * px) ** 2
    nbands = vrt.count
    dem = rasterio.open(A.dem) if A.model == "rgb_dem_sam" else None
    dem_nodata = (dem.nodata if dem is not None else None)
    cols, rows = offsets(W), offsets(H); ntiles = len(cols) * len(rows)
    log(f"[{A.model}] {A.ortho} -> {DST_CRS}: {W}x{H}, px~{px*1000:.1f} mm, "
        f"tile~{TILE*px:.1f} m -> {len(cols)}x{len(rows)}={ntiles} tiles (overlap {(TILE-STRIDE)*px:.2f} m)"
        + (f"  [smoke: max {A.max_tiles} tiles]" if A.max_tiles else ""))
    geoms, scores = [], []; done = 0; nprop = 0
    for tj in rows:
        for ti in cols:
            if A.max_tiles and done >= A.max_tiles: break
            win = Window(ti, tj, TILE, TILE); wt = vrt.window_transform(win)
            arr = vrt.read(indexes=[1, 2, 3] if nbands >= 3 else [1, 1, 1], window=win)
            img = np.transpose(arr, (1, 2, 0)).astype("uint8")          # HWC RGB
            done += 1
            if img.mean() < 3: continue

            # build the SAM input image for this tile (RGB, or RGB+height blend)
            sam_img = img
            if A.model == "rgb_dem_sam":
                wb = win_bounds(win, vrt.transform)
                dw = from_bounds(*wb, dem.transform)
                z = dem.read(1, window=dw, out_shape=(TILE, TILE),
                             resampling=Resampling.bilinear, boundless=True, fill_value=0).astype("float32")
                valid = np.isfinite(z) & (z > -3000)
                if dem_nodata is not None: valid &= (z != dem_nodata)
                if valid.mean() < 0.5: continue                         # DEM doesn't cover this tile
                z[~valid] = np.median(z[valid])
                hs = hillshade(z, cell=TILE * px / TILE)                # cell = px size (m)
                sam_img = (0.5 * img + 0.5 * hs[:, :, None]).astype("uint8")

            if A.model == "yolo_sam":
                # detector boxes -> box-prompted SAM
                res = det.predict(img[:, :, ::-1], conf=CONF, imgsz=1024, device=0,
                                  max_det=1000, verbose=False)[0]
                if len(res.boxes) == 0: continue
                xyxy = res.boxes.xyxy.cpu().numpy(); conf = res.boxes.conf.cpu().numpy()
                keep_boxes, keep_conf = [], []
                for (x0, y0, x1, y1), c in zip(xyxy, conf):
                    if (x0 <= MARGIN and ti > 0): continue
                    if (x1 >= TILE - MARGIN and ti + TILE < W): continue
                    if (y0 <= MARGIN and tj > 0): continue
                    if (y1 >= TILE - MARGIN and tj + TILE < H): continue
                    keep_boxes.append([x0, y0, x1, y1]); keep_conf.append(float(c))
                if not keep_boxes: continue
                nprop += len(keep_boxes)
                inp = tf.apply_image(img)
                t = torch.as_tensor(inp, device=DEV).permute(2, 0, 1).contiguous()[None]
                with torch.no_grad():
                    emb = sam.image_encoder(sam.preprocess(t))
                boxes_np = np.array(keep_boxes, dtype=np.float32)
                for s in range(0, len(boxes_np), 64):
                    masks = (predict_masks(emb, boxes_np[s:s+64]) > 0).cpu().numpy().astype("uint8")
                    for k, m in enumerate(masks):
                        best, ba = biggest_poly(m, wt)
                        if best is None or ba < 0.004 or ba > 0.5 * TILE_AREA: continue
                        geoms.append(best.simplify(0.003)); scores.append(keep_conf[s + k])
            else:
                # automatic mask generator (rgb_sam / rgb_dem_sam)
                for m in amg.generate(np.ascontiguousarray(sam_img)):
                    x, y, w, h = m["bbox"]
                    if (x <= MARGIN and ti > 0): continue
                    if (x + w >= TILE - MARGIN and ti + TILE < W): continue
                    if (y <= MARGIN and tj > 0): continue
                    if (y + h >= TILE - MARGIN and tj + TILE < H): continue
                    seg = m["segmentation"].astype("uint8")
                    best, ba = biggest_poly(seg, wt)
                    if best is None or ba < 0.004 or ba > 0.5 * TILE_AREA: continue
                    geoms.append(best.simplify(0.003))
                    scores.append(float(m["predicted_iou"]) * float(m["stability_score"]))
                    nprop += 1
            if done % 25 == 0:
                log(f"  {done}/{ntiles} tiles, {nprop} proposals, {len(geoms)} polys, {time.time()-t0:.0f}s")
        if A.max_tiles and done >= A.max_tiles: break
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
tree = STRtree([geoms[i] for i in valid_idx]); parent = list(range(len(geoms)))
def find(a):
    while parent[a] != a: parent[a] = parent[parent[a]]; a = parent[a]
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
        iou = inter / (areas[i] + areas[j] - inter); ios = inter / min(areas[i], areas[j])
        if iou > 0.5 or ios > 0.7: union(i, j)
groups = {}
for i in valid_idx: groups.setdefault(find(i), []).append(i)
keep = [max(members, key=lambda k: (scores[k], areas[k])) for members in groups.values()]
log(f"dedup: {len(valid_idx)} -> {len(keep)} polygons")
gpd.GeoDataFrame({"id": range(len(keep)), "score": scores[keep]},
                 geometry=[geoms[k] for k in keep], crs=DST_CRS).to_file(OUT, driver="GPKG")
log(f"wrote {OUT}  ({time.time()-t0:.0f}s)")
log("DONE")
