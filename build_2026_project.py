"""
Build + a QGIS project showing the 2026 drone ortho with the detector->SAM
predicted architecture layer. Run with QGIS python (python-qgis-ltr.bat).
"""
import os
from qgis.core import (
    QgsApplication, QgsProject, QgsRasterLayer, QgsVectorLayer,
    QgsCoordinateReferenceSystem, QgsFillSymbol, QgsReferencedRectangle,
)

REPO = r"C:\Users\Photogrammetry\AutomateSuSheetCreation"
ORTHO = os.path.join(REPO, "2026_GCP_Mapping.vrt")
PRED = os.path.join(REPO, "SAM_prototype", "sam_architecture_2026_detector.gpkg")
PROJ = os.path.join(REPO, "SAM_2026_detector.qgs")

QgsApplication.setPrefixPath(r"C:\Program Files\QGIS 3.40.8", True)
qgs = QgsApplication([], False); qgs.initQgis()

project = QgsProject.instance(); project.clear()
project.setCrs(QgsCoordinateReferenceSystem("EPSG:32632"))   # display CRS (predicted layer); ortho reprojects on the fly

ortho = QgsRasterLayer(ORTHO, "Drone ortho 2026")
if not ortho.isValid():
    raise RuntimeError("ortho invalid: " + ORTHO)
project.addMapLayer(ortho)

pred = QgsVectorLayer(PRED, "SAM predicted 2026 (detector->SAM)", "ogr")
if not pred.isValid():
    raise RuntimeError("predicted layer invalid: " + PRED)
pred.renderer().setSymbol(QgsFillSymbol.createSimple(
    {"color": "0,0,0,0", "outline_color": "255,0,0,255", "outline_width": "0.25"}))
project.addMapLayer(pred)

try:
    ext = pred.extent(); ext.scale(1.1)
    project.viewSettings().setDefaultViewExtent(
        QgsReferencedRectangle(ext, QgsCoordinateReferenceSystem("EPSG:32632")))
except Exception as e:
    print("view-extent set skipped:", e)

project.write(PROJ)
print("WROTE_PROJECT", PROJ)
qgs.exitQgis()
