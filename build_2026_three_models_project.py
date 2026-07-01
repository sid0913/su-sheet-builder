"""QGIS project comparing the THREE rock-mask models on the 2026 flight, one layer
each (2026 is a held-out season with no human labels, so this is model-vs-model):
  - yolo_sam      (detector -> SAM, rocks-only)         red
  - rgb_sam       (auto SAM on RGB, segment-everything) yellow
  - rgb_dem_sam   (auto SAM on RGB+hillshade blend)     cyan   <- DEM-fusion model
Basemap: full 2026 ortho (reprojected on the fly). View zooms to the DEM/trench crop
where all three overlap. Run with QGIS python (python-qgis-ltr.bat)."""
import os
from qgis.core import (QgsApplication, QgsProject, QgsRasterLayer, QgsVectorLayer,
                       QgsCoordinateReferenceSystem, QgsFillSymbol, QgsReferencedRectangle)

REPO = r"C:\Users\Photogrammetry\AutomateRockMask"
SAMP = os.path.join(REPO, "SAM_prototype")
ORTHO = os.path.join(REPO, "2026_GCP_Mapping.vrt")
PROJ = os.path.join(REPO, "SAM_2026_three_models.qgs")
LAYERS = [  # (gpkg, title, outline rgba)
    (os.path.join(SAMP, "sam_architecture_2026_detector.gpkg"),
     "2026 yolo_sam (detector->SAM, rocks-only)", "255,0,0,255"),
    (os.path.join(SAMP, "sam_architecture_2026_finetunedSAM_auto.gpkg"),
     "2026 rgb_sam (auto SAM, segment-everything)", "255,255,0,255"),
    (os.path.join(SAMP, "sam_architecture_2026_rgb_dem_sam.gpkg"),
     "2026 rgb_dem_sam (auto SAM, RGB+hillshade fusion)", "0,255,255,255"),
]

QgsApplication.setPrefixPath(r"C:\Program Files\QGIS 3.40.8", True)
qgs = QgsApplication([], False); qgs.initQgis()
project = QgsProject.instance(); project.clear()
project.setCrs(QgsCoordinateReferenceSystem("EPSG:32632"))

ortho = QgsRasterLayer(ORTHO, "Drone ortho 2026")
if not ortho.isValid(): raise RuntimeError("ortho invalid: " + ORTHO)
project.addMapLayer(ortho)

zoom_to = None
for path, title, rgba in LAYERS:
    if not os.path.exists(path):
        print("SKIP missing:", path); continue
    lyr = QgsVectorLayer(path, title, "ogr")
    if not lyr.isValid(): raise RuntimeError("layer invalid: " + path)
    lyr.renderer().setSymbol(QgsFillSymbol.createSimple(
        {"color": "0,0,0,0", "outline_color": rgba, "outline_width": "0.2"}))
    project.addMapLayer(lyr)
    if "rgb_dem_sam" in path:  # smallest extent (trench) -> best default view
        zoom_to = lyr

try:
    ext = (zoom_to or ortho).extent(); ext.scale(1.2)
    project.viewSettings().setDefaultViewExtent(
        QgsReferencedRectangle(ext, QgsCoordinateReferenceSystem("EPSG:32632")))
except Exception as e:
    print("view set skipped:", e)

project.write(PROJ)
print("WROTE_PROJECT", PROJ)
qgs.exitQgis()
