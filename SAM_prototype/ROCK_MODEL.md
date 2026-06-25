# Rock-Only Architecture Model (YOLO + fine-tuned SAM)

Automatic stone/rock mapping for the TARP excavation: feed a georeferenced drone
ortho, get a GIS polygon layer outlining every individual stone/architectural
feature — a draft of the hand-digitized `Architecture_YYYY.shp` layer.

It is a **rock-only model**: a single detection class (every masonry feature is
"rock/stone"). The original archaeological `Type` (Block, Wall, Street, Tile,
Column, Cistern, …) is **not** predicted by the model — it is preserved as
training metadata only, to be assigned later by a separate classifier or by hand.

---

## 1. What it does

Drone ortho (RGB, georeferenced)  →  **polygon layer**, one polygon per stone, in
EPSG:32632, seam-free, deduplicated.

Two stages chained together:

1. **Detector — where are the stones?** A YOLOv8m model trained on the
   hand-labelled stones (all 3 years, all types merged into one "feature" class).
   It outputs a box around each stone it sees.
2. **Segmenter — trace each stone.** Segment Anything (SAM, ViT-H) with a
   **fine-tuned mask decoder**. For each detector box it produces the precise
   polygon outline of that stone.

Around the two stages, a **seam-free tiling wrapper**:
- reproject the ortho to UTM 32N on the fly (WarpedVRT) so all maths is in metres;
- cut into **overlapping** 1024-px tiles (stride 768 ≈ 1 m overlap) so a stone cut
  by one tile's edge is captured whole in the neighbour;
- **drop boxes touching an interior tile seam** (kept only at the true image edge);
- run detector + SAM per tile;
- **checkpoint** the raw polygons, then **dedup** overlap duplicates by
  IoU / containment, keeping the highest-confidence polygon.

---

## 2. Why "rock-only" (single class)

The labels are ~90 % `Block` with a long tail of rare types (Floor, Column,
Cistern, Groove, Removed … 3–9 examples each across all years — far too few to
train a per-class detector). So:

- **Detection / segmentation = 1 class** ("rock/stone/feature"). Robust, and it is
  the part that delivers ~all the value (finding + outlining stones).
- **Type classification = deferred.** Every box's source `Type` is stored in
  `yolo_dataset/types.json` so a later step (e.g. Random Forest on the labelled
  years) can assign Type without retraining the detector. Rare types stay manual.

---

## 3. Files

Weights (on disk, **gitignored** — repo tracks only `.py`):

| Role | Path |
|---|---|
| Detector (trained) | `SAM_prototype/yolo_runs/feature_detector/weights/best.pt` |
| SAM decoder (fine-tuned, multi-year) — used by the pipeline | `SAM_prototype/sam_decoder_multiyear.pth` |
| SAM decoder (fine-tuned, 2025-only, earlier) | `SAM_prototype/sam_decoder_finetuned.pth` |
| Base SAM ViT-H (frozen encoder) | `~/.cache/torch/hub/checkpoints/sam_vit_h_4b8939.pth` |

Scripts (committed):

| Script | Purpose |
|---|---|
| `prep_yolo_dataset.py` | Build the 1-class YOLO detection dataset from `Architecture_{2023,2024,2025}.shp` over their orthos. Keeps all types; writes `types.json`. |
| `train_detector.py` | Train YOLOv8m (single class). |
| `finetune_sam.py` / `train_multiyear.py` | Fine-tune the SAM mask decoder (box-prompted) on the stones. |
| `run_detector_sam.py` | **The model runner**: `python run_detector_sam.py <ortho> <out.gpkg>`. |
| `predict_viz.py` | Render detector predictions vs ground truth. |
| `build_2025_detector_project.py` / `build_2026_project.py` | Build QGIS projects to view results. |

Environment: a CUDA venv at `C:\Users\Photogrammetry\sv`
(torch 2.5.1+cu121, segment-geospatial, ultralytics). **Must** sit at a short path
(Windows MAX_PATH) — see project memory.

---

## 4. How to run on a new flight

```bash
# 1. (GPU) detect + segment -> polygons
"C:/Users/Photogrammetry/sv/Scripts/python.exe" \
    SAM_prototype/run_detector_sam.py \
    "path/to/new_ortho.tif" \
    "SAM_prototype/sam_architecture_NEW.gpkg"

# 2. View in QGIS (edit paths in the builder, run under QGIS python)
"C:/Program Files/QGIS 3.40.8/bin/python-qgis-ltr.bat" build_2026_project.py
```

The runner is CRS-agnostic (WarpedVRT reprojects any input to UTM 32N). It writes
a `_raw.gpkg` checkpoint before dedup, and **skips re-segmentation** if that
checkpoint already exists (so dedup can be re-tuned cheaply).

Key knob: `CONF` (detector confidence, default **0.25**) in `run_detector_sam.py`.
Raise it for fewer, cleaner, higher-precision polygons; lower it for more coverage.

---

## 5. How it was trained

**Dataset** (`prep_yolo_dataset.py`): 1024-px tiles over the 3 years' orthos ∩
their `Architecture` labels → 191 tiles / 6,834 boxes (single class). 80/20
train/val by tile. `types.json` keeps each box's original Type.

**Detector** (`train_detector.py`): YOLOv8m, imgsz 1024, AdamW lr0=0.001, cosine
LR, warmup 5, light aug (flip/rotate/scale), early-stop patience 30.
Best = **epoch 73: mAP50 0.482, mAP50-95 0.253, P 0.606, R 0.449**.
(mAP is *deflated* by label sparsity — humans didn't box every stone, so the
detector's real-but-unlabelled hits count as false positives.)

**SAM decoder** (`train_multiyear.py`): freeze ViT-H encoder + prompt encoder;
train only the mask decoder with box prompts (stone bbox) and Dice+BCE loss on the
rasterized polygon. Combined 2023+2024+2025, 80/20 tile split.
Held-out test mean mask IoU **0.663 → 0.750** (acc@IoU0.5 80 % → 92 %).

---

## 6. Results

| Run | Polygons | Reference | Notes |
|---|---|---|---|
| **2026 flight** (held-out season) | **2,778** | human 2023-25: 1,496-3,049 | ~4 min, 928 tiles; no 2026 labels (visual check) |
| **2025** | **2,665** | 2,774 human (same extent) | 43 % human stones matched @IoU≥0.5, 60 % area; 2025 was IN training |

vs. blind SAM "segment everything" (no detector): ~16,812 over-segmented polygons.
The detector front-end is what collapses that to a human-ballpark count and stops
it segmenting vegetation / open ground.

---

## 7. Limitations & next steps

- **Per-stone boundary precision** is the weak point (mean IoU ~0.36 vs 2025 human;
  ~31 % at IoU≥0.7). Good enough for a reviewable draft, not a finished layer.
- **No Type** — single class by design; needs the separate classifier step.
- **RGB only** — a co-registered **DSM/hillshade** channel is the biggest untried
  lever for separating adjacent same-stone blocks (joints are height edges).
- **Sparse/selective human labels** both deflate the detector's mAP and the
  IoU-match metric (it finds correct stones the humans never labelled).
- More labelled data + LoRA fine-tuning of the SAM image encoder would lift IoU.
