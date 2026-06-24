"""
Seam-free SAM segmentation via OVERLAPPING tiles + dedup.
- Tiles overlap neighbours (stride < tile), so any object clipped at one tile's
  seam is captured whole in an adjacent tile's interior.
- Masks touching an INTERIOR tile border are dropped (kills background 'square'
  masks; keeps masks at the true image edge).
- Remaining duplicates from overlap zones are merged by IoU/containment dedup.
CHECKPOINTED: raw polygons saved before the (fragile) dedup, and segmentation is
skipped if the raw checkpoint already exists.
Output: SAM_prototype/sam_architecture_2025_overlap.gpkg (EPSG:32632)
"""
import os, time
import numpy as np
import torch
import rasterio
from rasterio.windows import Window
from rasterio.features import shapes
import geopandas as gpd
from shapely.geometry import shape
from shapely.strtree import STRtree
from shapely.validation import make_valid
from segment_anything import sam_model_registry, SamAutomaticMaskGenerator

SP = os.path.dirname(os.path.abspath(__file__))
REPO = r"C:\Users\Photogrammetry\AutomateRockMask"
OVERLAP = os.path.join(SP, "overlap.tif")
CKPT = os.path.expanduser(r"~/.cache/torch/hub/checkpoints/sam_vit_h_4b8939.pth")
FT = os.path.join(SP, "sam_decoder_multiyear.pth")
OUT = os.path.join(REPO, "SAM_prototype", "sam_architecture_2025_overlap.gpkg")
RAW_OUT = os.path.join(REPO, "SAM_prototype", "sam_architecture_2025_overlap_raw.gpkg")
DEV = "cuda"; TILE = 1024; STRIDE = 768; MARGIN = 3   # px

def log(*a): print(*a, flush=True)

t0 = time.time()
src = rasterio.open(OVERLAP)
W, H = src.width, src.height
TILE_AREA = (TILE * abs(src.transform.a)) ** 2

def offsets(total):
    o = list(range(0, total - TILE + 1, STRIDE))
    if not o or o[-1] != total - TILE:
        o.append(total - TILE)
    return sorted(set(o))

# ---------- Phase 1: segmentation (checkpointed) ----------
if os.path.exists(RAW_OUT):
    log(f"loading cached raw polygons from {RAW_OUT} (skipping segmentation) ...")
    rawg = gpd.read_file(RAW_OUT)
    geoms = list(rawg.geometry.values)
    scores = list(rawg["score"].values) if "score" in rawg.columns else [1.0] * len(geoms)
    log(f"  loaded {len(geoms)} raw polygons")
else:
    log("loading SAM vit_h + fine-tuned decoder ...")
    sam = sam_model_registry["vit_h"](checkpoint=CKPT).to(DEV)
    sam.mask_decoder.load_state_dict(torch.load(FT, map_location=DEV))
    sam.eval()
    amg = SamAutomaticMaskGenerator(
        sam, points_per_side=48, pred_iou_thresh=0.80, stability_score_thresh=0.88,
        crop_n_layers=0, min_mask_region_area=120)
    cols, rows = offsets(W), offsets(H)
    ntiles = len(cols) * len(rows)
    log(f"raster {W}x{H} | tile {TILE} stride {STRIDE} -> {len(cols)}x{len(rows)}={ntiles} tiles "
        f"(overlap {TILE-STRIDE}px ~ {(TILE-STRIDE)*abs(src.transform.a):.2f} m)")
    geoms, scores = [], []
    done = 0
    for tj in rows:
        for ti in cols:
            win = Window(ti, tj, TILE, TILE); wt = src.window_transform(win)
            img = np.transpose(src.read(window=win), (1, 2, 0))
            if img.shape[2] > 3: img = img[:, :, :3]
            if img.shape[2] == 1: img = np.repeat(img, 3, 2)
            done += 1
            if img.mean() < 3: continue
            masks = amg.generate(np.ascontiguousarray(img))
            for m in masks:
                x, y, w, h = m["bbox"]
                if (x <= MARGIN and ti > 0): continue
                if (x + w >= TILE - MARGIN and ti + TILE < W): continue
                if (y <= MARGIN and tj > 0): continue
                if (y + h >= TILE - MARGIN and tj + TILE < H): continue
                seg = m["segmentation"].astype("uint8")
                best = None; barea = 0
                for g, v in shapes(seg, mask=seg.astype(bool), transform=wt):
                    p = shape(g)
                    if p.area > barea: best, barea = p, p.area
                if best is None or barea < 0.004 or barea > 0.5 * TILE_AREA:
                    continue
                geoms.append(best.simplify(0.003))
                scores.append(float(m["predicted_iou"]) * float(m["stability_score"]))
            if done % 25 == 0:
                log(f"  {done}/{ntiles} tiles, {len(geoms)} raw polys, {time.time()-t0:.0f}s")
    # CHECKPOINT raw polygons BEFORE the fragile dedup so segmentation is never lost
    gpd.GeoDataFrame({"id": range(len(geoms)), "score": scores},
                     geometry=geoms, crs="EPSG:32632").to_file(RAW_OUT, driver="GPKG")
    log(f"raw kept (border-filtered): {len(geoms)} -> saved {RAW_OUT}  ({time.time()-t0:.0f}s)")

# ---------- Phase 2: validate + dedup (robust) ----------
log("validating geometries ...")
fixed = []
for g in geoms:
    try:
        if g is None or g.is_empty:
            fixed.append(None); continue
        fixed.append(g if g.is_valid else make_valid(g))
    except Exception:
        fixed.append(None)
geoms = fixed
scores = np.asarray(scores, dtype=float)
areas = np.array([g.area if g is not None else 0.0 for g in geoms])

log("dedup ...")
valid_idx = [i for i, g in enumerate(geoms) if g is not None and areas[i] > 0]
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
                 geometry=[geoms[k] for k in keep], crs="EPSG:32632").to_file(OUT, driver="GPKG")
log(f"wrote {OUT}  ({time.time()-t0:.0f}s)")
log("DONE")
