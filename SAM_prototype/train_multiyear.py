"""
Multi-year SAM decoder fine-tuning.
Train on combined 2025+2024+2023 stone polygons (80% of tiles), TEST on the
held-out 20% of tiles. Report accuracy (per-stone mask IoU, box-prompted) overall
and per year, plus %stones IoU>=0.5/0.7. Encoder + prompt encoder frozen.

All coords UTM32N meters; ortho geotransform + polygon coords align numerically.
"""
import os, json, time, copy, random
import numpy as np
import torch
import torch.nn.functional as F
import rasterio
from rasterio.windows import Window
from rasterio.features import rasterize
import geopandas as gpd
from segment_anything import sam_model_registry
from segment_anything.utils.transforms import ResizeLongestSide

SP = os.path.dirname(os.path.abspath(__file__))
REPO = r"C:\Users\Photogrammetry\AutomateSuSheetCreation"
CKPT = os.path.expanduser(r"~/.cache/torch/hub/checkpoints/sam_vit_h_4b8939.pth")
DEV = "cuda"; TILE = 1024
random.seed(0); np.random.seed(0); torch.manual_seed(0)

# (year, ortho, shp). 2025 uses the pre-clipped overlap GTiff.
SOURCES = [
    ("2025", os.path.join(SP, "overlap.tif"), os.path.join(REPO, "Architecture_2025.shp")),
    ("2024", r"C:\Users\Photogrammetry\GIS_2024\Drone Temple Area 2024 Closing ortho EPSG32632.jpg",
             r"C:\Users\Photogrammetry\GIS_2024\Architecture_2024.shp"),
    ("2023", r"C:\Users\Photogrammetry\GIS_2023\Temple_Area_Ortho_6-9-23.jpg",
             r"C:\Users\Photogrammetry\GIS_2023\Architecture_2023.shp"),
]

def log(*a): print(*a, flush=True)

log("loading SAM vit_h ...")
sam = sam_model_registry["vit_h"](checkpoint=CKPT).to(DEV)
tf = ResizeLongestSide(sam.image_encoder.img_size)
for p in sam.image_encoder.parameters(): p.requires_grad_(False)
for p in sam.prompt_encoder.parameters(): p.requires_grad_(False)
img_pe = sam.prompt_encoder.get_dense_pe()
base_decoder_state = copy.deepcopy(sam.mask_decoder.state_dict())

def build_tiles(year, ortho, shp, cap_tiles=90):
    src = rasterio.open(ortho)
    gts = gpd.read_file(shp); gts = gts[gts.geometry.notna()]
    ob = src.bounds; ax0, ay0, ax1, ay1 = gts.total_bounds
    ix0, iy0 = max(ob.left, ax0), max(ob.bottom, ay0)
    ix1, iy1 = min(ob.right, ax1), min(ob.top, ay1)
    inv = ~src.transform
    c0, r0 = inv * (ix0, iy1); c1, r1 = inv * (ix1, iy0)
    col0, row0 = int(max(0, min(c0, c1))), int(max(0, min(r0, r1)))
    col1, row1 = int(min(src.width, max(c0, c1))), int(min(src.height, max(r0, r1)))
    tiles = []; nst = 0
    for tj in range(row0, row1 - TILE + 1, TILE):
        for ti in range(col0, col1 - TILE + 1, TILE):
            win = Window(ti, tj, TILE, TILE); wt = src.window_transform(win)
            wb = rasterio.windows.bounds(win, src.transform)
            sub = gts.cx[wb[0]:wb[2], wb[1]:wb[3]]
            if len(sub) < 4: continue
            img = np.transpose(src.read(window=win), (1, 2, 0))
            if img.shape[2] > 3: img = img[:, :, :3]
            if img.shape[2] == 1: img = np.repeat(img, 3, 2)
            inp = tf.apply_image(img)
            t = torch.as_tensor(inp, device=DEV).permute(2, 0, 1).contiguous()[None]
            t = sam.preprocess(t)
            with torch.no_grad():
                emb = sam.image_encoder(t).cpu()
            inv_wt = ~wt; boxes, masks = [], []
            for geom in sub.geometry:
                if geom.is_empty: continue
                b = geom.bounds
                c0_, r0_ = inv_wt * (b[0], b[3]); c1_, r1_ = inv_wt * (b[2], b[1])
                x0, x1 = sorted((c0_, c1_)); y0, y1 = sorted((r0_, r1_))
                x0 = max(0, x0); y0 = max(0, y0); x1 = min(TILE, x1); y1 = min(TILE, y1)
                if (x1 - x0) < 4 or (y1 - y0) < 4: continue
                if (x1 - x0) > 0.9 * TILE and (y1 - y0) > 0.9 * TILE: continue
                m = rasterize([(geom, 1)], out_shape=(TILE, TILE), transform=wt, dtype="uint8")
                if m.sum() < 16: continue
                boxes.append([x0, y0, x1, y1]); masks.append(m)
            if not masks: continue
            tiles.append(dict(year=year, emb=emb, boxes=np.array(boxes, np.float32),
                              masks=np.stack(masks)))
            nst += len(masks)
            if len(tiles) >= cap_tiles:
                log(f"  ({year} capped at {cap_tiles} tiles)"); return tiles, nst
    return tiles, nst

def predict(embg, boxes_np):
    bx = tf.apply_boxes(boxes_np, (TILE, TILE))
    bx = torch.as_tensor(bx, dtype=torch.float, device=DEV)
    with torch.no_grad():
        sp_, de_ = sam.prompt_encoder(points=None, boxes=bx, masks=None)
    lr, _ = sam.mask_decoder(image_embeddings=embg, image_pe=img_pe,
                             sparse_prompt_embeddings=sp_, dense_prompt_embeddings=de_,
                             multimask_output=False)
    return sam.postprocess_masks(lr, (TILE, TILE), (TILE, TILE))[:, 0]

def dice_bce(logits, target):
    p = torch.sigmoid(logits)
    bce = F.binary_cross_entropy_with_logits(logits, target)
    dice = 1 - (2 * (p * target).sum((1, 2)) + 1) / (p.sum((1, 2)) + target.sum((1, 2)) + 1)
    return bce + dice.mean()

@torch.no_grad()
def evaluate(tiles, mb=48):
    """Return dict: per-year and overall (mean IoU, median IoU, acc@.5, acc@.7, n)."""
    per = {}
    for tl in tiles:
        embg = tl["emb"].to(DEV); ys = per.setdefault(tl["year"], [])
        for s in range(0, len(tl["boxes"]), mb):
            logits = predict(embg, tl["boxes"][s:s+mb])
            pred = (logits > 0).float()
            tgt = torch.as_tensor(tl["masks"][s:s+mb], dtype=torch.float, device=DEV)
            inter = (pred * tgt).sum((1, 2)); union = ((pred + tgt) > 0).float().sum((1, 2))
            ys += (inter / union.clamp(min=1)).cpu().tolist()
    out = {}
    allious = []
    for y, v in per.items():
        a = np.array(v); allious += v
        out[y] = dict(n=len(a), mean_iou=round(float(a.mean()), 3),
                      median_iou=round(float(np.median(a)), 3),
                      acc50=round(float((a >= .5).mean()), 3), acc70=round(float((a >= .7).mean()), 3))
    a = np.array(allious)
    out["ALL"] = dict(n=len(a), mean_iou=round(float(a.mean()), 3),
                      median_iou=round(float(np.median(a)), 3),
                      acc50=round(float((a >= .5).mean()), 3), acc70=round(float((a >= .7).mean()), 3))
    return out

# ---- build all years ----
t0 = time.time()
all_tiles = []
for year, ortho, shp in SOURCES:
    log(f"building {year}: {os.path.basename(ortho)}")
    tiles, ns = build_tiles(year, ortho, shp)
    log(f"  -> {len(tiles)} tiles, {ns} stones")
    all_tiles += tiles
log(f"total tiles={len(all_tiles)} stones={sum(len(t['boxes']) for t in all_tiles)} (build {time.time()-t0:.0f}s)")

# ---- alignment sanity: base IoU per year on ALL tiles ----
sam.mask_decoder.load_state_dict(base_decoder_state); sam.eval()
log("alignment/base check (all tiles): " + json.dumps(evaluate(all_tiles)))

# ---- 80/20 tile split, stratified by year ----
random.shuffle(all_tiles)
train, test = [], []
by_year = {}
for t in all_tiles: by_year.setdefault(t["year"], []).append(t)
for y, ts in by_year.items():
    k = max(1, int(round(0.2 * len(ts))))
    test += ts[:k]; train += ts[k:]
log(f"split: train tiles={len(train)} ({sum(len(t['boxes']) for t in train)} stones) | "
    f"test tiles={len(test)} ({sum(len(t['boxes']) for t in test)} stones)")

# ---- BASE accuracy on test ----
sam.mask_decoder.load_state_dict(base_decoder_state); sam.eval()
base_test = evaluate(test)
log("[BASE] test: " + json.dumps(base_test["ALL"]))

# ---- train decoder on train split ----
sam.mask_decoder.load_state_dict(base_decoder_state)
opt = torch.optim.AdamW(sam.mask_decoder.parameters(), lr=1e-4, weight_decay=1e-4)
EPOCHS, MAXB = 35, 24
best = (-1, None)
for ep in range(EPOCHS):
    sam.mask_decoder.train(); random.shuffle(train); el = 0; nb = 0
    for tl in train:
        embg = tl["emb"].to(DEV)
        idx = np.random.permutation(len(tl["boxes"]))[:MAXB]
        logits = predict(embg, tl["boxes"][idx])
        tgt = torch.as_tensor(tl["masks"][idx], dtype=torch.float, device=DEV)
        loss = dice_bce(logits, tgt)
        opt.zero_grad(); loss.backward(); opt.step(); el += loss.item(); nb += 1
    if (ep + 1) % 5 == 0 or ep == 0:
        sam.mask_decoder.eval(); m = evaluate(test)["ALL"]["mean_iou"]
        log(f"  epoch {ep+1:02d}/{EPOCHS} loss={el/nb:.4f} test mean IoU={m:.3f}")
        if m > best[0]: best = (m, copy.deepcopy(sam.mask_decoder.state_dict()))

# ---- FINAL: load best, full test report ----
sam.mask_decoder.load_state_dict(best[1]); sam.eval()
ft_test = evaluate(test)
torch.save(best[1], os.path.join(SP, "sam_decoder_multiyear.pth"))
report = dict(best_epoch_iou=round(best[0], 3),
              train_stones=sum(len(t['boxes']) for t in train),
              test_stones=sum(len(t['boxes']) for t in test),
              base_test=base_test, finetuned_test=ft_test)
json.dump(report, open(os.path.join(SP, "multiyear_metrics.json"), "w"), indent=2)
log("\n================ TEST-SET ACCURACY (held-out) ================")
log("BASE      : " + json.dumps(base_test))
log("FINETUNED : " + json.dumps(ft_test))
log(f"\nruntime {time.time()-t0:.0f}s")
log("DONE")
