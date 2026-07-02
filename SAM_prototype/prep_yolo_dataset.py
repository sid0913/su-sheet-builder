"""
Build a single-class object-detection dataset (YOLO format) for an
'architectural feature' detector, from the hand-digitized Architecture_*.shp of
2023/2024/2025 over their drone orthos.

- ONE detection class ("feature") but EVERY polygon is kept, including rare types
  (Column, Cistern, Floor, ...). The original Type is preserved in types.json so
  nothing is lost for a later classification step.
- Non-overlapping 1024-px tiles; tiles with >=1 feature are written.
- 80/20 train/val split by tile. Also renders a 20-tile preview with GT boxes.
Output: SAM_prototype/yolo_dataset/{images,labels}/{train,val}/, data.yaml, types.json
"""
import os, json, random
import numpy as np
import rasterio
from rasterio.windows import Window
import geopandas as gpd
from PIL import Image
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

random.seed(0); np.random.seed(0)
SP = os.path.dirname(os.path.abspath(__file__))
REPO = r"C:\Users\Photogrammetry\AutomateSuSheetCreation"
SCRATCH = r"C:\Users\PHOTOG~1\AppData\Local\Temp\claude\c--Users-Photogrammetry-AutomateSuSheetCreation\e14cd478-34db-4a60-87d1-8ce4439fe5ad\scratchpad"
OUT = os.path.join(SP, "yolo_dataset")
TILE, STRIDE, MINBOX = 1024, 1024, 4   # px

SOURCES = [
    ("2025", os.path.join(SCRATCH, "overlap.tif"), os.path.join(REPO, "Architecture_2025.shp")),
    ("2024", r"C:\Users\Photogrammetry\GIS_2024\Drone Temple Area 2024 Closing ortho EPSG32632.jpg",
             r"C:\Users\Photogrammetry\GIS_2024\Architecture_2024.shp"),
    ("2023", r"C:\Users\Photogrammetry\GIS_2023\Temple_Area_Ortho_6-9-23.jpg",
             r"C:\Users\Photogrammetry\GIS_2023\Architecture_2023.shp"),
]

for sub in ("images/train", "images/val", "labels/train", "labels/val"):
    os.makedirs(os.path.join(OUT, sub), exist_ok=True)

def log(*a): print(*a, flush=True)

# ---- collect tiles (image array + list of (box_norm, type)) ----
tiles = []
type_hist = {}
for year, ortho, shp in SOURCES:
    src = rasterio.open(ortho)
    g = gpd.read_file(shp); g = g[g.geometry.notna()]
    tcol = "Type" if "Type" in g.columns else ("type" if "type" in g.columns else None)
    ob = src.bounds; ax0, ay0, ax1, ay1 = g.total_bounds
    ix0, iy0 = max(ob.left, ax0), max(ob.bottom, ay0)
    ix1, iy1 = min(ob.right, ax1), min(ob.top, ay1)
    inv = ~src.transform
    c0, r0 = inv * (ix0, iy1); c1, r1 = inv * (ix1, iy0)
    col0, row0 = int(max(0, min(c0, c1))), int(max(0, min(r0, r1)))
    col1, row1 = int(min(src.width, max(c0, c1))), int(min(src.height, max(r0, r1)))
    n_year = 0
    for tj in range(row0, row1 - TILE + 1, STRIDE):
        for ti in range(col0, col1 - TILE + 1, STRIDE):
            win = Window(ti, tj, TILE, TILE); wt = src.window_transform(win)
            wb = rasterio.windows.bounds(win, src.transform)
            sub = g.cx[wb[0]:wb[2], wb[1]:wb[3]]
            if len(sub) == 0: continue
            inv_wt = ~wt; boxes = []
            for _, row in sub.iterrows():
                geom = row.geometry
                if geom.is_empty: continue
                b = geom.bounds
                cc0, rr0 = inv_wt * (b[0], b[3]); cc1, rr1 = inv_wt * (b[2], b[1])
                x0, x1 = sorted((cc0, cc1)); y0, y1 = sorted((rr0, rr1))
                x0 = max(0, x0); y0 = max(0, y0); x1 = min(TILE, x1); y1 = min(TILE, y1)
                if (x1 - x0) < MINBOX or (y1 - y0) < MINBOX: continue
                t = str(row[tcol]) if tcol else "feature"
                boxes.append(((x0, y0, x1, y1), t))
                type_hist[t] = type_hist.get(t, 0) + 1
            if not boxes: continue
            img = np.transpose(src.read(window=win), (1, 2, 0))
            if img.shape[2] > 3: img = img[:, :, :3]
            if img.shape[2] == 1: img = np.repeat(img, 3, 2)
            if img.mean() < 3: continue
            tiles.append(dict(name=f"{year}_{ti}_{tj}", img=img.astype("uint8"), boxes=boxes))
            n_year += 1
    log(f"{year}: {n_year} tiles")

random.shuffle(tiles)
nval = max(1, int(round(0.2 * len(tiles))))
val_set = set(id(t) for t in tiles[:nval])
log(f"total tiles={len(tiles)}  train={len(tiles)-nval} val={nval}  total boxes={sum(len(t['boxes']) for t in tiles)}")
log("type histogram (all kept): " + json.dumps(dict(sorted(type_hist.items(), key=lambda x:-x[1]))))

# ---- write images + labels (+ type sidecar) ----
types_sidecar = {}
for t in tiles:
    split = "val" if id(t) in val_set else "train"
    Image.fromarray(t["img"]).save(os.path.join(OUT, "images", split, t["name"] + ".png"))
    lines, tys = [], []
    for (x0, y0, x1, y1), ty in t["boxes"]:
        cx = (x0 + x1) / 2 / TILE; cy = (y0 + y1) / 2 / TILE
        w = (x1 - x0) / TILE; h = (y1 - y0) / TILE
        lines.append(f"0 {cx:.6f} {cy:.6f} {w:.6f} {h:.6f}")
        tys.append(ty)
    with open(os.path.join(OUT, "labels", split, t["name"] + ".txt"), "w") as f:
        f.write("\n".join(lines))
    types_sidecar[t["name"]] = tys
json.dump(types_sidecar, open(os.path.join(OUT, "types.json"), "w"))

with open(os.path.join(OUT, "data.yaml"), "w") as f:
    f.write(f"path: {OUT}\ntrain: images/train\nval: images/val\nnc: 1\nnames:\n  0: feature\n")
log("wrote dataset to " + OUT)

# ---- 20-tile preview with GT boxes ----
sample = random.sample(tiles, min(20, len(tiles)))
fig, ax = plt.subplots(4, 5, figsize=(25, 20))
for a, t in zip(ax.ravel(), sample):
    a.imshow(t["img"]); a.set_title(f"{t['name']}  ({len(t['boxes'])} feat)", fontsize=8)
    a.set_xticks([]); a.set_yticks([])
    for (x0, y0, x1, y1), ty in t["boxes"]:
        a.add_patch(mpatches.Rectangle((x0, y0), x1 - x0, y1 - y0, fill=False,
                    edgecolor="lime", linewidth=0.5))
for a in ax.ravel()[len(sample):]:
    a.axis("off")
plt.tight_layout()
prev = os.path.join(SP, "yolo_tiles_preview.png")
plt.savefig(prev, dpi=110, bbox_inches="tight")
log("wrote preview " + prev)
