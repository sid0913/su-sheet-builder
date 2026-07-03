"""
Prototype: SAM 'segment everything' on a drone-ortho patch, compared to the
hand-digitized Architecture_2025 ground truth in the same patch.

RGB-only (no DSM available). Patch: 12x12 m @ ~3.94 mm/px, EPSG:32632.
"""
import os, sys, time, json
import numpy as np

SP = os.path.dirname(os.path.abspath(__file__))
ORTHO = os.path.join(SP, "patch_ortho.tif")
GT_GPKG = os.path.join(SP, "arch_gt_patch.gpkg")
MASKS_TIF = os.path.join(SP, "sam_masks.tif")
PRED_GPKG = os.path.join(SP, "sam_pred.gpkg")
FIG = os.path.join(SP, "compare.png")
METRICS = os.path.join(SP, "metrics.json")

t0 = time.time()
import torch
print("torch", torch.__version__, "cuda", torch.cuda.is_available(), flush=True)
from samgeo import SamGeo

# ---- 1. Run SAM automatic mask generator -------------------------------------
# Stones ~10-30 cm => ~25-75 px. Push point density up and keep small regions.
sam = SamGeo(
    model_type="vit_h",
    automatic=True,
    sam_kwargs=dict(
        points_per_side=64,
        pred_iou_thresh=0.86,
        stability_score_thresh=0.90,
        crop_n_layers=1,
        crop_n_points_downscale_factor=2,
        min_mask_region_area=80,   # px; drop tiny noise (~1.3 cm^2)
    ),
)
print("generating masks... (GPU)", flush=True)
sam.generate(ORTHO, output=MASKS_TIF, foreground=False, unique=True)
print("generate done in %.1fs" % (time.time() - t0), flush=True)

# vectorize predicted masks -> polygons in raster CRS
sam.tiff_to_vector(MASKS_TIF, PRED_GPKG)
print("vectorized -> %s" % PRED_GPKG, flush=True)

# ---- 2. Compare to ground truth ---------------------------------------------
import geopandas as gpd
from shapely.validation import make_valid
import rasterio
from rasterio.plot import reshape_as_image

gt = gpd.read_file(GT_GPKG)
pred = gpd.read_file(PRED_GPKG)
if pred.crs is None:
    pred = pred.set_crs(gt.crs)
pred = pred.to_crs(gt.crs)

gt["geometry"] = gt.geometry.apply(make_valid)
pred["geometry"] = pred.geometry.apply(make_valid)

# clip both to the exact patch box so border effects don't skew counts
with rasterio.open(ORTHO) as ds:
    b = ds.bounds
    box_geom = gpd.GeoSeries.from_wkt(
        [f"POLYGON(({b.left} {b.bottom},{b.right} {b.bottom},"
         f"{b.right} {b.top},{b.left} {b.top},{b.left} {b.bottom}))"],
        crs=gt.crs)[0]

gt = gt[gt.intersects(box_geom)].copy()
# Remove SAM's giant "background" tile(s): anything covering >25% of the patch
patch_area = box_geom.area
pred["area"] = pred.geometry.area
pred = pred[(pred.area > 0.0008) & (pred.area < 0.25 * patch_area)].copy()  # 8 cm^2 .. 25% patch

print(f"GT polygons: {len(gt)}   PRED polygons (filtered): {len(pred)}", flush=True)

# IoU-based greedy matching via spatial index
sindex = pred.sindex
matched_pred = set()
ious = []
tp = 0
for gidx, g in gt.geometry.items():
    cand = list(sindex.intersection(g.bounds))
    best_iou, best_j = 0.0, -1
    for j in cand:
        if j in matched_pred:
            continue
        p = pred.geometry.iloc[j]
        if not p.intersects(g):
            continue
        inter = g.intersection(p).area
        union = g.area + p.area - inter
        iou = inter / union if union > 0 else 0
        if iou > best_iou:
            best_iou, best_j = iou, j
    ious.append(best_iou)
    if best_iou >= 0.5:
        tp += 1
        matched_pred.add(best_j)

ng, npd = len(gt), len(pred)
recall = tp / ng if ng else 0
precision = tp / npd if npd else 0
f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0

# area coverage: fraction of GT stone area overlapped by any predicted mask
pred_union = pred.geometry.union_all() if hasattr(pred.geometry, "union_all") else pred.geometry.unary_union
gt_union = gt.geometry.union_all() if hasattr(gt.geometry, "union_all") else gt.geometry.unary_union
coverage = gt_union.intersection(pred_union).area / gt_union.area if gt_union.area else 0

metrics = dict(
    gt_count=ng, pred_count=npd, tp_iou50=tp,
    precision_iou50=round(precision, 3), recall_iou50=round(recall, 3), f1_iou50=round(f1, 3),
    mean_best_iou=round(float(np.mean(ious)), 3), median_best_iou=round(float(np.median(ious)), 3),
    gt_area_coverage=round(coverage, 3),
)
print(json.dumps(metrics, indent=2), flush=True)
json.dump(metrics, open(METRICS, "w"), indent=2)

# ---- 3. Side-by-side visualization ------------------------------------------
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

with rasterio.open(ORTHO) as ds:
    img = reshape_as_image(ds.read())
    ext = [ds.bounds.left, ds.bounds.right, ds.bounds.bottom, ds.bounds.top]

fig, ax = plt.subplots(1, 3, figsize=(24, 8))
for a in ax:
    a.imshow(img, extent=ext)
    a.set_xlim(ext[0], ext[1]); a.set_ylim(ext[2], ext[3])
    a.set_xticks([]); a.set_yticks([])
ax[0].set_title("Drone ortho (4 mm/px)")
gt.boundary.plot(ax=ax[1], color="cyan", linewidth=0.6)
ax[1].set_title(f"Ground truth (hand-digitized)  n={ng}")
pred.boundary.plot(ax=ax[2], color="yellow", linewidth=0.5)
ax[2].set_title(f"SAM auto-segmentation  n={npd}")
plt.tight_layout()
plt.savefig(FIG, dpi=130, bbox_inches="tight")
print("wrote", FIG, flush=True)
print("TOTAL %.1fs" % (time.time() - t0), flush=True)
