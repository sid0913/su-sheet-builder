"""
QGIS project comparing detector->SAM predicted 2025 architecture vs the human
Architecture_2025 labels over the 2025 drone ortho.
Run with QGIS python (python-qgis-ltr.bat).
"""
import os
from qgis.core import (
    QgsApplication, QgsProject, QgsRasterLayer, QgsVectorLayer,
    QgsCoordinateReferenceSystem, QgsFillSymbol, QgsReferencedRectangle,
)

REPO = r"C:\Users\Photogrammetry\AutomateRockMask"
ORTHO = os.path.join(REPO, "GCP-Drone-Flight-2025.jpg")
PRED = os.path.join(REPO, "SAM_prototype", "sam_architecture_2025_detector.gpkg")
HUMAN = os.path.join(REPO, "Architecture_2025.shp")
PROJ = os.path.join(REPO, "SAM_2025_detector_vs_human.qgs")

QgsApplication.setPrefixPath(r"C:\Program Files\QGIS 3.40.8", True)
qgs = QgsApplication([], False); qgs.initQgis()

project = QgsProject.instance(); project.clear()
project.setCrs(QgsCoordinateReferenceSystem("EPSG:32632"))

ortho = QgsRasterLayer(ORTHO, "Drone ortho 2025")
if not ortho.isValid():
    raise RuntimeError("ortho invalid: " + ORTHO)
project.addMapLayer(ortho)

human = QgsVectorLayer(HUMAN, "Architecture 2025 (human)", "ogr")
if not human.isValid():
    raise RuntimeError("human invalid: " + HUMAN)
human.renderer().setSymbol(QgsFillSymbol.createSimple(
    {"color": "0,0,0,0", "outline_color": "0,255,255,255", "outline_width": "0.25"}))
project.addMapLayer(human)

pred = QgsVectorLayer(PRED, "SAM predicted 2025 (detector->SAM)", "ogr")
if not pred.isValid():
    raise RuntimeError("predicted invalid: " + PRED)
pred.renderer().setSymbol(QgsFillSymbol.createSimple(
    {"color": "0,0,0,0", "outline_color": "255,0,0,255", "outline_width": "0.25"}))
project.addMapLayer(pred)

try:
    ext = human.extent(); ext.scale(1.1)
    project.viewSettings().setDefaultViewExtent(
        QgsReferencedRectangle(ext, QgsCoordinateReferenceSystem("EPSG:32632")))
except Exception as e:
    print("view-extent set skipped:", e)

project.write(PROJ)
print("WROTE_PROJECT", PROJ)
qgs.exitQgis()
