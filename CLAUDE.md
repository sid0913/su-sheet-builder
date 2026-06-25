# AutomateRockMask — project notes

Automated generation of archaeological **SU sheets** (QGIS PDF reports) and
research into **auto-digitizing the stone-architecture layer** from drone orthos
at the TARP (Tharros) excavation. All spatial data is **EPSG:32632** (UTM 32N).

CUDA work (SAM, YOLO, U-Nets) runs in a dedicated venv at **`C:\Users\Photogrammetry\sv`**
(PyTorch 2.5.1+cu121, segment-geospatial, ultralytics, segmentation-models-pytorch) on
the RTX 4090. It must stay at a short path (Windows MAX_PATH). The GPU is shared with
the user's Metashape/MeshLab work — **only launch heavy GPU jobs when the GPU is free.**

---

## Auto-digitizing the architecture layer — THREE MODELS (toggle)

One runner, one flag — **`SAM_prototype/run_rock_mask.py --model {yolo_sam,rgb_sam,rgb_dem_sam}`**:

```bash
"C:/Users/Photogrammetry/sv/Scripts/python.exe" SAM_prototype/run_rock_mask.py \
    --model yolo_sam  <ortho.tif> SAM_prototype/out.gpkg          # rocks-only, ≈human count
    --model rgb_sam   <ortho.tif> SAM_prototype/out.gpkg          # segment-everything
    --model rgb_dem_sam <ortho.tif> SAM_prototype/out.gpkg --dem <DEM.tif>   # RGB+height fusion
# (--max-tiles N for a quick smoke test)
```

All three reuse the **same multi-year fine-tuned SAM decoder**
(`SAM_prototype/sam_decoder_multiyear.pth`, trained on 2025+2024+2023 hand-labelled
stones; box-prompted **0.75 mean IoU, 92% of stones at IoU≥0.5**) and the same
overlap-tiling + drop-seam-masks + IoU/containment **dedup** post-processing. They
differ only in **how stones are proposed** (detector boxes vs. automatic point grid)
and **what feeds SAM** (RGB vs. RGB+height blend).

### `yolo_sam` — YOLO detector → SAM  (RECOMMENDED for an automatic layer)
- A trained **YOLOv8m "feature" detector** proposes boxes; the fine-tuned SAM refines
  each box into a polygon. **Segments ONLY rocks/stones** (ignores ground/rubble/veg).
- **Count: ~2.8k polygons, the human ballpark** (2025=3049, 2024=2211, 2023=1496). Clean.
- Detector: AdamW lr0=0.001 cosine, warmup 5; best epoch 73 **mAP50 0.482, P 0.61, R 0.45**
  (mAP deflated — humans didn't box every stone, so real detections score as FPs).
  Weights `SAM_prototype/yolo_runs/feature_detector/weights/best.pt` (gitignored).
- Dataset/train: `prep_yolo_dataset.py` (+ `types.json`), `train_detector.py`.
- **Outputs:** `sam_architecture_{2025,2026}_detector.gpkg`.
- **Projects:** `SAM_2025_detector_vs_human.qgs`, `SAM_2026_detector.qgs`.
- Tradeoff: detector recall (~45%) means some stones are missed.

### `rgb_sam` — Fine-tuned SAM, automatic (segment-everything)
- SAM's automatic mask generator drops a point grid over every tile; the fine-tuned
  decoder masks each. **Segments the whole scene** — stones *and* ground/rubble/veg.
- **Count: very high, ~13k–17k polygons** (vs human ~3k); over-segments. Best boundary
  fidelity but noisy — use as a refiner, then review & prune.
- **Outputs:** `sam_architecture_2025_overlap.gpkg`, `sam_architecture_2026_finetunedSAM_auto.gpkg`.
- **Projects:** `SAM_2025_finetunedSAM_auto.qgs`, `SAM_2026_finetunedSAM_auto.qgs`.

### `rgb_dem_sam` — DEM-fusion: RGB+hillshade → automatic SAM
- Same as `rgb_sam`, but each tile's RGB is blended 50/50 with a **hillshade computed
  on-the-fly from a co-registered DEM** (`--dem`). Only valid where the DEM covers the
  ortho (e.g. the 2025/2026 trench crop). Output `sam_architecture_{year}_rgb_dem_sam.gpkg`.
- **It is NOT better than RGB** — kept as a selectable option. The `worktree-dem-fusion`
  experiment asked whether height helps SAM and the answer was no:
  box-prompted IoU **RGB 0.62 vs fused 0.63** (noise), fine-tuned **RGB 0.747 vs 0.742**,
  automatic recall **RGB 0.221 vs fused 0.179** (RGB wins). See *How rgb_dem_sam was
  generated* in `SAM_prototype/ROCK_MODEL.md` §8.

| | yolo_sam | rgb_sam | rgb_dem_sam |
|---|---|---|---|
| Proposes via | detector boxes | auto point grid | auto point grid |
| SAM input | RGB | RGB | RGB + hillshade blend |
| Finds stones | **rocks only** | everything | everything (DEM area only) |
| Polygon count | **~2.8k** (≈ human) | ~13k–17k (over-seg) | ~13k–17k (over-seg) |
| Needs a DEM | no | no | **yes** |
| Best for | automatic layer near human | refining / max fidelity | (experimental; ≈ rgb_sam) |

Notes:
- YOLO `train()`/inference on Windows must be guarded by `if __name__ == "__main__":`
  (DataLoader spawn). The runner reprojects any input to UTM 32N on the fly (rasterio
  `WarpedVRT`), so a EPSG:4326 ortho is fine. Training `Type` is preserved in
  `yolo_dataset/types.json` for later per-stone classification (Block/Wall/Street/…),
  which no model assigns yet.
- Legacy per-model scripts (`run_detector_sam.py`, `run_detector_sam_2026.py`) still
  work but are superseded by `run_rock_mask.py`.
