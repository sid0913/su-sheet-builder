"""
Remove tile-seam 'boundary square' artifacts from the SAM 2025 layer.
A polygon is dropped if it is large AND has a bbox edge lying on a 1024-px tile
seam (i.e. a background mask clipped at a tile border), or if it is absurdly large.
Writes a cleaned gpkg + before/after figure.
"""
import os, numpy as np, geopandas as gpd, rasterio
from rasterio.windows import from_bounds
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt

REPO = r"C:\Users\Photogrammetry\AutomateSuSheetCreation"
SP = r"C:\Users\PHOTOG~1\AppData\Local\Temp\claude\c--Users-Photogrammetry-AutomateSuSheetCreation\e14cd478-34db-4a60-87d1-8ce4439fe5ad\scratchpad"
IN = REPO + r"\SAM_prototype\sam_architecture_2025.gpkg"
OUT = REPO + r"\SAM_prototype\sam_architecture_2025_clean.gpkg"
OVL = SP + r"\overlap.tif"
TILE = 1024

g = gpd.read_file(IN)
with rasterio.open(OVL) as ds:
    tr = ds.transform; W, H = ds.width, ds.height
px = abs(tr.a); left, top = tr.c, tr.f
seam_x = [left + k * TILE * px for k in range(W // TILE + 1)]
seam_y = [top - k * TILE * px for k in range(H // TILE + 1)]
tol = 2.5 * px   # ~1 cm

b = g.geometry.bounds
a = g.geometry.area.values
def near(vals, seams):
    v = vals.values[:, None]; s = np.array(seams)[None, :]
    return (np.abs(v - s) < tol).any(axis=1)
on_seam = near(b.minx, seam_x) | near(b.maxx, seam_x) | near(b.miny, seam_y) | near(b.maxy, seam_y)

# artifact = (large & touches a tile seam) OR (absurdly large)
artifact = ((a > 0.30) & on_seam) | (a > 3.0)
clean = g[~artifact].copy()
print(f"input={len(g)}  dropped={int(artifact.sum())}  kept={len(clean)}")
print(f"  dropped large+on-seam={int(((a>0.30)&on_seam).sum())}  dropped huge(>3m2)={int((a>3.0).sum())}")
clean.to_file(OUT, driver="GPKG")
print("wrote", OUT)

# before/after over a 16x16 m window
x0, y0, x1, y1 = 452206, 4413794, 452222, 4413810
with rasterio.open(OVL) as ds:
    win = from_bounds(x0, y0, x1, y1, ds.transform)
    img = np.transpose(ds.read(window=win), (1, 2, 0))[:, :, :3]
fig, ax = plt.subplots(1, 2, figsize=(17, 8))
for A in ax:
    A.imshow(img, extent=[x0, x1, y0, y1]); A.set_xlim(x0, x1); A.set_ylim(y0, y1)
    A.set_xticks([]); A.set_yticks([])
g.boundary.plot(ax=ax[0], color="red", linewidth=0.4); ax[0].set_title(f"BEFORE (n={len(g)})")
clean.boundary.plot(ax=ax[1], color="red", linewidth=0.4); ax[1].set_title(f"AFTER cleaned (n={len(clean)})")
plt.tight_layout(); plt.savefig(SP + r"\clean_beforeafter.png", dpi=120)
print("wrote clean_beforeafter.png")
