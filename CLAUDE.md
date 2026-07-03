# AutomateSuSheetCreation — project notes

> Repo renamed from **AutomateRockMask** (2026). It covers two things: **SU-sheet PDF
> generation** (the primary pipeline — see "SU Sheet generation pipeline" below) and
> **rock-mask / architecture auto-digitizing** research (the SAM/YOLO section that follows).

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

### Full rock-mask pipeline: drone ortho → architecture shapefile
Each season, produce the stone/architecture layer from the new drone ortho — the first pass that
used to be hours of hand-tracing in QGIS. `SAM_prototype/ROCK_MODEL.md` is the deep model card
(training, metrics, DEM-fusion experiment); **the operational steps are here.**

**0. Input ortho — use the georeferenced PNG, NOT the TIF.** The model needs a *georeferenced*
RGB raster (it reprojects the source CRS → UTM 32N via WarpedVRT, so the input **must** carry a
CRS/geotransform). Feed the **aligned PNG through its `.vrt`** (e.g. `2026_GCP_Mapping.vrt`,
which wraps `2026_GCP_Mapping.png`). **Do not feed the raw `.tif`** — the TIF is **slightly
shifted**, so its polygons land off-position; the PNG/`.vrt` was re-aligned to the correct
coordinates. A plain PNG/JPG with **no** world file/`.vrt`/CRS will not work.

**1. Place the weights** (gitignored — back them up off-repo; on a fresh clone drop each at the
exact path `run_rock_mask.py` reads — see ROCK_MODEL.md §3 "Large files"). No retrain needed
unless you've hand-labelled a new season:
- YOLO detector: `SAM_prototype/yolo_runs/feature_detector/weights/best.pt` (~207 MB)
- Fine-tuned SAM decoder (multi-year, used by all 3 models): `SAM_prototype/sam_decoder_multiyear.pth` (~16 MB)
- Base SAM ViT-H (frozen encoder, auto-downloaded): `~/.cache/torch/hub/checkpoints/sam_vit_h_4b8939.pth`

**2. Run `yolo_sam`** — GPU must be free; use the `sv` CUDA venv, **not** QGIS Python. Output is a
GeoPackage in EPSG:32632:
```bash
"C:/Users/Photogrammetry/sv/Scripts/python.exe" SAM_prototype/run_rock_mask.py \
    --model yolo_sam 2026_GCP_Mapping.vrt SAM_prototype/sam_architecture_YYYY_detector.gpkg
```
Writes a `_raw.gpkg` checkpoint before dedup and **skips re-segmentation if that checkpoint exists**
(re-tune dedup cheaply). Knob: `CONF` (detector confidence, default 0.25) — raise for fewer/cleaner
polygons, lower for coverage. ~4 min for a full flight on the 4090.

**3. Convert the GeoPackage to a shapefile** so it drops straight into the QGIS projects (the
SU-sheet architecture layer and the `build_*_project.py` viewers both take a layer path; `.shp`
matches the hand-digitized `Architecture_YYYY.shp` convention). Run under any env with GDAL
(QGIS Python or the `sv` venv), or use QGIS *Export → Save Features As → ESRI Shapefile*:
```bash
ogr2ogr -f "ESRI Shapefile" SAM_prototype/sam_architecture_YYYY_detector.shp \
    SAM_prototype/sam_architecture_YYYY_detector.gpkg
```
(The `.gpkg` already loads directly in QGIS too — `build_2026_three_models_project.py` adds it via
`QgsVectorLayer(..., "ogr")`; the `.shp` step is for using it as the SU-sheet architecture layer.)

**4. Load / review in QGIS**: build a viewer project (`build_2026_project.py` /
`build_2026_three_models_project.py` — edit paths, run under QGIS Python), eyeball against the ortho,
prune stragglers; use the result as the draft `Architecture_YYYY`.

**5. Rare types stay manual**: the model is single-class ("rock") and assigns **no `Type`** — the
SU-sheet architecture QML styles on `Type`, so hand-label rare features (Cistern, Column, Street, …)
and populate `Type` where needed; too few training examples to learn them.

**6. Retrain only when you add a hand-labelled season**, all in the `sv` venv:
`prep_yolo_dataset.py` (rebuild 1-class tiles + `types.json` from `Architecture_{years}.shp`) →
`train_detector.py` (YOLOv8m) → `train_multiyear.py` (fine-tune the SAM decoder). YOLO
`train()`/inference on Windows must be under `if __name__ == "__main__":` (DataLoader spawn).

---

## SU Sheet generation pipeline

The other half of this repo: generating per-SU QGIS **PDF "SU sheets"**. Two files —
`generate_su_sheets.py` (driver) → `qgs_su_sheets_utils.py` (all QGIS logic). Normally
driven by the **tarp-lab dashboard**'s *Create SU Sheet* button, not run by hand.

### How a run works
1. The dashboard writes `su_sheets_input.json` (`{"year", "items":[{"su","job_id"}]}`)
   into the repo dir and launches the driver under **QGIS's bundled Python** via
   `C:\Program Files\QGIS 3.40.8\bin\python-qgis-ltr.bat`. The `sv` CUDA venv cannot run it.
2. `generate_su_sheets.py` loops the items. Per SU it derives
   `trench = "Trench " + su[-5:-3] + "000"` (so `SU_22035` → `Trench 22000`); `job_id` is the
   SU's **top-pgram** Metashape job number. It emits `progress.json` per SU (dashboard bar),
   wraps each SU in try/except → `error_log.txt`, and **skips any SU whose
   `Volumetrics_{year}/{SU}.pdf` already exists** — to regenerate, delete/move the old PDF first.
3. `generate_SU_Sheet()` loads the season project `TARP_SU_Sheets_{year}.qgs`, clears & rebuilds
   all layers (ortho, DEM+contours, SU shapefile, architecture, trench boundaries, overview-zoom),
   then `SUSheet` loads `SU_Layout_Templates/SU_Template_{trench}.qpt`, frames the 4 map pages,
   exports the PDF to `Volumetrics_{year}/{SU}.pdf`, and `project.write()`s the project back
   (why each season gets its own `.qgs`).

### Draw-order invariant (don't regress)
Each map's stack is set explicitly via `setLayers` (index 0 = top) in `_setup_map_page()`:
**trench-boundaries always above architecture**; architecture directly below the SU-top layer and
directly above the drone imagery (the ortho on the Ortho map, the drone-flight raster on the DEM
map). The per-page order **opacities → SU style → zoom+scalebar → setLayers → lock** is
load-bearing — locking freezes each map before the next page mutates shared layer opacities.

### Running / regenerating by hand
From the repo dir: stage `su_sheets_input.json`, move aside any existing target PDFs, then
`"C:\Program Files\QGIS 3.40.8\bin\python-qgis-ltr.bat" generate_su_sheets.py`. ~A few minutes per SU.

### New-season rollover (`YYYY`)
Adding a season = one `YEAR_CONFIG` entry + data files in place + trench templates. `year` is threaded
through `generate_SU_Sheet()`; most paths derive from it, the rest live in **`YEAR_CONFIG`** (top of
`qgs_su_sheets_utils.py`).

1. **Archive last season** (frozen runnable copy): `cp generate_su_sheets.py generate_su_sheets_<last>.py`
   and `cp qgs_su_sheets_utils.py qgs_su_sheets_utils_<last>.py`; in the archived driver, repoint the
   import to the archived utils. **These `*_<year>.py` files are intentional archives — do not delete.**
2. **Driver**: `YEAR="YYYY"`; `QGS_FILE_NAME="TARP_SU_Sheets_YYYY.qgs"` (copy any existing project — it's
   cleared/rebuilt on read then written back); replace the SU/job list (the dashboard normally writes it).
3. **`YEAR_CONFIG["YYYY"]`**: `drone_flight`, `architecture`, `trench_boundaries` — the three inputs whose
   names don't follow the `{name}_{year}` pattern.
4. **Data in place**:
   - `GIS_YYYY/3D_SU_Shapefiles/` — auto-built from the OBJ on first run; **requires Blender + the
     BlenderGIS addon** (`generate_top_shp.py` shells out to Blender headless).
   - `Volumetrics_YYYY/SU Top OBJs/<SU>_top.obj` (input). `Volumetrics_YYYY/` is **also the output dir**
     for the generated PDFs (auto-created).
   - `GIS_YYYY/Orthos/` — per-job `.jpg`, matched on the exact digits after `Job_` (regex, tolerates a
     trailing `_SU…` suffix — e.g. both `Pgram_Job_798.jpg` and `Pgram_Job_784_SU22001.jpg`).
   - `GIS_YYYY/DEM/` — per-job `.tif`, matched the same way.
5. **Trench boundaries**: merge the per-trench clipping boundaries into one 2D-Polygon EPSG:32632
   shapefile with an integer `Trench` field, named `TARP YYYY Trench Boundaries.shp` (via `ogr2ogr`; see
   git history for the exact commands). **To change one trench mid-season**: replace that record's geometry
   in the merged file and refresh `Trench_{t}_Overview_Zoom_Rough_Boundary.shp` (a copy of the clipping
   boundary), then regenerate that trench's SUs.
6. **Trench templates**: one `SU_Layout_Templates/SU_Template_{trench}.qpt` per trench (copy one, swap the
   layout `name=` and the title text — extents/UUIDs are overridden at runtime). Picked automatically by
   trench number.
7. **Overview-zoom boundaries** (repo root, one per trench, NOT year-threaded):
   `Trench_{t}_Overview_Zoom_Rough_Boundary.shp` — a copy of the trench clipping boundary; frames the
   Overview map at buffer 0 (exact extent).
7b. **Drone-flight background**: 2026 switched from the raw `.tif` to an edited PNG wrapped in a
   georeferenced **`.vrt`** (EPSG:32632 + overviews) — the `.tif` is slightly **shifted**, the
   PNG/`.vrt` is aligned to the correct coordinates (same reason the rock-mask model reads the
   `.vrt`, see "Full rock-mask pipeline" above). Co-locate `*_GCP_Mapping.{vrt,png,png.ovr,pgw,prj}`
   in the repo root, point `drone_flight` at the `.vrt`, and set the same `.vrt` as `ORTHO` in the SAM
   `build_*_project.py`. Earlier seasons used a plain `.jpg`; either works.
8. **Sanity check**: `"C:\Program Files\QGIS 3.40.8\apps\Python312\python.exe" -m py_compile
   generate_su_sheets.py qgs_su_sheets_utils.py`. QGIS Python is **3.12** (the driver uses 3.12-only
   nested f-strings, so the 3.9 `sv` venv rejects it). On Git Bash the `/c/Program Files/...` form works.

### Per-season asset inventory
| Asset | Convention / source | Selected by |
|---|---|---|
| SU shapefiles | `GIS_{year}/3D_SU_Shapefiles/<SU>_EPSG_32632.shp` (Blender-built from OBJ) | `year` |
| SU Top OBJs | `Volumetrics_{year}/SU Top OBJs/<SU>_top.obj` | `year` |
| SU sheet PDFs (output) | `Volumetrics_{year}/<SU>.pdf` | `year` |
| Orthos | `GIS_{year}/Orthos/…Job_{job}….jpg` | job number (regex) |
| DEMs | `GIS_{year}/DEM/…Job_{job}….tif` | job number (regex) |
| Drone-flight background | `.vrt` (2026+) or `.jpg`, repo root | `YEAR_CONFIG[...]["drone_flight"]` |
| Architecture polygons | no fixed pattern; layer `Type` must match a QML category | `YEAR_CONFIG[...]["architecture"]` |
| Trench boundaries (merged) | `TARP {year} Trench Boundaries.shp` | `YEAR_CONFIG[...]["trench_boundaries"]` |
| Architecture style | shared across years | `ARCHITECTURE_STYLE` |
| SU styles (per page) | `Styles/SU_Pink / Ortho_SU_view_yellow_outline / SU_black_outline.qml` | `STYLE_SU_*` |
| Trench templates | `SU_Layout_Templates/SU_Template_{trench}.qpt` | trench # |
| Overview-zoom boundary | `Trench_{trench}_Overview_Zoom_Rough_Boundary.shp` (repo root) | trench # |
| Base project | `TARP_SU_Sheets_{year}.qgs` | `QGS_FILE_NAME` (driver) |

### Hardcoded values to check on a machine/tooling change
- `QGS_PROGRAM_PATH` and the `_QGIS_PATHS` list (`qgs_su_sheets_utils.py`) + the launcher/Python-3.12
  paths above — bump on a QGIS upgrade; also `scripts.qgis_launcher` / `scripts.create_su_sheet*` in the
  dashboard `config.yaml`.
- `PATH = "C:\Users\Photogrammetry"` in the driver; the repo-name path in `error_log.txt`,
  `create_shp_files_in_bulk_from_volumetrics.py`, and the `build_*_project.py` `REPO=` constants.
- Site constants `DELTA_X=452000`, `DELTA_Y=4413000`, EPSG:32632 in `generate_top_shp.py` (Tharros /
  UTM 32N — change only if the site or zone changes).

### Known quirks
- The template item is misspelled **`Scalebar Overivew Page 1`**; the code matches that spelling — fix
  both or neither.
- Page 4's DEM map reuses **`Scalebar Overview Page 2`** (there is no `Scalebar DEM Page 4` in the
  template) — verify it doesn't mis-size the page-2 scalebar before "fixing".
- `bandStatistics()` / `hasStatistics()` are deprecated in QGIS 3.40 but still valid; revisit on upgrade.
