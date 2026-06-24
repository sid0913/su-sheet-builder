"""
Fine-tune SAM (vit_h) mask decoder on hand-digitized stone polygons.
- Image encoder + prompt encoder FROZEN; only mask decoder trained.
- Prompt = each stone's bounding box; target = rasterized polygon.
- Held-out test = the 12x12 m eval patch (excluded from training).
- Reports per-stone mask IoU: BASE vs FINE-TUNED on the test patch.
RGB-only (no DSM). EPSG:32632.
"""
import os, sys, time, json, copy, random
import numpy as np
import torch
import torch.nn.functional as F
import rasterio
from rasterio.windows import Window
from rasterio.features import rasterize
import geopandas as gpd
from shapely.geometry import box as shp_box
from segment_anything import sam_model_registry
from segment_anything.utils.transforms import ResizeLongestSide

random.seed(0); np.random.seed(0); torch.manual_seed(0)
SP = os.path.dirname(os.path.abspath(__file__))
REPO = r"C:\Users\Photogrammetry\AutomateRockMask"
OVERLAP = os.path.join(SP, "overlap.tif")
SHP = os.path.join(REPO, "Architecture_2025.shp")
CKPT = os.path.expanduser(r"~/.cache/torch/hub/checkpoints/sam_vit_h_4b8939.pth")
DEV = "cuda"
TILE = 1024
# test patch (held out)
TX0, TY0, TX1, TY1 = 452206, 4413794, 452218, 4413806

def log(*a):
    print(*a, flush=True)

t0 = time.time()
log("loading SAM vit_h ...")
sam = sam_model_registry["vit_h"](checkpoint=CKPT).to(DEV)
tf = ResizeLongestSide(sam.image_encoder.img_size)
for p in sam.image_encoder.parameters(): p.requires_grad_(False)
for p in sam.prompt_encoder.parameters(): p.requires_grad_(False)

gts = gpd.read_file(SHP)
gts = gts[gts.geometry.notna()].copy()

src = rasterio.open(OVERLAP)
W, H = src.width, src.height
test_geom = shp_box(TX0, TY0, TX1, TY1)

# ---- build tiles ----
def stones_in_window(win_transform, win_bounds):
    minx, miny, maxx, maxy = win_bounds
    sub = gts.cx[minx:maxx, miny:maxy]
    out = []
    for geom in sub.geometry:
        if geom.is_empty: continue
        b = geom.bounds
        # pixel bbox via inverse transform
        inv = ~win_transform
        c0, r0 = inv * (b[0], b[3]); c1, r1 = inv * (b[2], b[1])
        x0, x1 = sorted((c0, c1)); y0, y1 = sorted((r0, r1))
        x0 = max(0, x0); y0 = max(0, y0); x1 = min(TILE, x1); y1 = min(TILE, y1)
        if (x1 - x0) < 4 or (y1 - y0) < 4: continue
        if (x1 - x0) > 0.9 * TILE and (y1 - y0) > 0.9 * TILE: continue  # skip near-tile-size
        out.append((geom, [x0, y0, x1, y1]))
    return out

train_tiles, test_tiles = [], []
ncol, nrow = W // TILE, H // TILE
for tj in range(nrow):
    for ti in range(ncol):
        win = Window(ti * TILE, tj * TILE, TILE, TILE)
        wt = src.window_transform(win)
        wb = rasterio.windows.bounds(win, src.transform)
        wgeom = shp_box(wb[0], wb[1], wb[2], wb[3])
        stones = stones_in_window(wt, wb)
        if len(stones) < 4: continue
        rec = (ti, tj, win, wt, stones)
        if wgeom.intersects(test_geom):
            test_tiles.append(rec)
        else:
            train_tiles.append(rec)
log(f"tiles: train={len(train_tiles)} test={len(test_tiles)} "
    f"(stones train={sum(len(r[4]) for r in train_tiles)}, test={sum(len(r[4]) for r in test_tiles)})")

# ---- precompute frozen embeddings + rasterized masks per tile ----
def load_tile(rec):
    ti, tj, win, wt, stones = rec
    img = src.read(window=win)            # 3xTILExTILE uint8
    img = np.transpose(img, (1, 2, 0))    # HWC
    if img.shape[2] > 3: img = img[:, :, :3]
    inp = tf.apply_image(img)
    t = torch.as_tensor(inp, device=DEV).permute(2, 0, 1).contiguous()[None]
    t = sam.preprocess(t)
    with torch.no_grad():
        emb = sam.image_encoder(t)        # 1x256x64x64
    masks, boxes = [], []
    for geom, bb in stones:
        m = rasterize([(geom, 1)], out_shape=(TILE, TILE), transform=wt,
                      fill=0, all_touched=False, dtype="uint8")
        if m.sum() < 16: continue
        masks.append(m); boxes.append(bb)
    if not masks: return None
    return emb.cpu(), np.array(boxes, dtype=np.float32), np.stack(masks)

log("precomputing embeddings (frozen encoder) ...")
def materialize(tiles):
    data = []
    for k, rec in enumerate(tiles):
        d = load_tile(rec)
        if d is not None: data.append(d)
        if (k + 1) % 20 == 0: log(f"  ...{k+1}/{len(tiles)} tiles")
    return data
train_data = materialize(train_tiles)
test_data = materialize(test_tiles)
log(f"materialized train={len(train_data)} test={len(test_data)} in {time.time()-t0:.0f}s")

img_pe = sam.prompt_encoder.get_dense_pe()

def predict_masks(emb_gpu, boxes_np, orig=(TILE, TILE)):
    """Run prompt+decoder for N boxes sharing one embedding. Returns logits NxTILExTILE."""
    bx = tf.apply_boxes(boxes_np, orig)
    bx = torch.as_tensor(bx, dtype=torch.float, device=DEV)
    with torch.no_grad():
        sparse, dense = sam.prompt_encoder(points=None, boxes=bx, masks=None)
    lr, _ = sam.mask_decoder(
        image_embeddings=emb_gpu,   # (1,256,64,64); decoder repeat_interleaves to B internally
        image_pe=img_pe,
        sparse_prompt_embeddings=sparse,
        dense_prompt_embeddings=dense,
        multimask_output=False)
    hr = sam.postprocess_masks(lr, input_size=(TILE, TILE), original_size=orig)  # Nx1xHxW
    return hr[:, 0]

def dice_bce(logits, target):
    p = torch.sigmoid(logits)
    bce = F.binary_cross_entropy_with_logits(logits, target)
    dice = 1 - (2 * (p * target).sum((1, 2)) + 1) / (p.sum((1, 2)) + target.sum((1, 2)) + 1)
    return bce + dice.mean()

@torch.no_grad()
def eval_iou(data, max_box=64):
    ious = []
    for emb, boxes, masks in data:
        emb = emb.to(DEV)
        for s in range(0, len(boxes), max_box):
            bb = boxes[s:s+max_box]; mm = masks[s:s+max_box]
            logits = predict_masks(emb, bb)
            pred = (logits > 0).float()
            tgt = torch.as_tensor(mm, dtype=torch.float, device=DEV)
            inter = (pred * tgt).sum((1, 2))
            union = ((pred + tgt) > 0).float().sum((1, 2))
            ious += (inter / union.clamp(min=1)).cpu().tolist()
    return float(np.mean(ious)), float(np.median(ious)), len(ious)

# ---- BASE eval ----
sam.eval()
base_mean, base_med, n_test = eval_iou(test_data)
log(f"[BASE]  test stones={n_test}  mean IoU={base_mean:.3f}  median IoU={base_med:.3f}")

# ---- train decoder ----
opt = torch.optim.AdamW(sam.mask_decoder.parameters(), lr=1e-4, weight_decay=1e-4)
EPOCHS = 40
MAXB = 24   # boxes per step
sam.mask_decoder.train()
step = 0
for ep in range(EPOCHS):
    random.shuffle(train_data)
    ep_loss = 0.0; nb = 0
    for emb, boxes, masks in train_data:
        emb = emb.to(DEV)
        idx = np.random.permutation(len(boxes))[:MAXB]
        bb = boxes[idx]; mm = masks[idx]
        logits = predict_masks(emb, bb)
        tgt = torch.as_tensor(mm, dtype=torch.float, device=DEV)
        loss = dice_bce(logits, tgt)
        opt.zero_grad(); loss.backward(); opt.step()
        ep_loss += loss.item(); nb += 1; step += 1
    if (ep + 1) % 5 == 0 or ep == 0:
        sam.mask_decoder.eval()
        m, md, _ = eval_iou(test_data)
        sam.mask_decoder.train()
        log(f"  epoch {ep+1:02d}/{EPOCHS}  loss={ep_loss/max(nb,1):.4f}  test mean IoU={m:.3f}")

# ---- FINAL eval ----
sam.mask_decoder.eval()
ft_mean, ft_med, _ = eval_iou(test_data)
log(f"[FINETUNED] test stones={n_test}  mean IoU={ft_mean:.3f}  median IoU={ft_med:.3f}")

torch.save(sam.mask_decoder.state_dict(), os.path.join(SP, "sam_decoder_finetuned.pth"))
metrics = dict(
    test_stones=n_test, train_stones=sum(len(b) for _, b, _ in train_data),
    base_mean_iou=round(base_mean, 3), base_median_iou=round(base_med, 3),
    finetuned_mean_iou=round(ft_mean, 3), finetuned_median_iou=round(ft_med, 3),
    abs_gain=round(ft_mean - base_mean, 3),
    rel_gain_pct=round(100 * (ft_mean - base_mean) / max(base_mean, 1e-6), 1),
    epochs=EPOCHS, runtime_s=round(time.time() - t0, 0),
)
json.dump(metrics, open(os.path.join(SP, "finetune_metrics.json"), "w"), indent=2)
log(json.dumps(metrics, indent=2))

# ---- qualitative figure on a few test stones ----
try:
    import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
    emb, boxes, masks = max(test_data, key=lambda d: len(d[1]))
    embg = emb.to(DEV)
    sel = list(range(min(6, len(boxes))))
    bb = boxes[sel]
    # base needs original decoder; reload a base model decoder
    base = sam_model_registry["vit_h"](checkpoint=CKPT).to(DEV); base.eval()
    def pred_with(model, embg, bb):
        bx = tf.apply_boxes(bb, (TILE, TILE)); bx = torch.as_tensor(bx, dtype=torch.float, device=DEV)
        with torch.no_grad():
            sp_, de_ = model.prompt_encoder(points=None, boxes=bx, masks=None)
            lr, _ = model.mask_decoder(image_embeddings=embg,
                                       image_pe=model.prompt_encoder.get_dense_pe(),
                                       sparse_prompt_embeddings=sp_, dense_prompt_embeddings=de_,
                                       multimask_output=False)
            hr = model.postprocess_masks(lr, (TILE, TILE), (TILE, TILE))
        return (hr[:, 0] > 0).cpu().numpy()
    pb = pred_with(base, embg, bb); pf = pred_with(sam, embg, bb)
    fig, ax = plt.subplots(3, len(sel), figsize=(3*len(sel), 9))
    for i, s in enumerate(sel):
        ax[0, i].imshow(masks[s], cmap="gray"); ax[0, i].set_title("GT");
        ax[1, i].imshow(pb[i], cmap="gray"); ax[1, i].set_title("base")
        ax[2, i].imshow(pf[i], cmap="gray"); ax[2, i].set_title("finetuned")
        for r in range(3): ax[r, i].set_xticks([]); ax[r, i].set_yticks([])
    plt.tight_layout(); plt.savefig(os.path.join(SP, "finetune_masks.png"), dpi=110)
    log("wrote finetune_masks.png")
except Exception as e:
    log("viz skipped:", e)
log(f"TOTAL {time.time()-t0:.0f}s")
