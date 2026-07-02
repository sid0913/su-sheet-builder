"""
Build a QGIS project comparing SAM-predicted vs human-labelled architecture
over the 2025 drone ortho. Run with QGIS python (python-qgis-ltr.bat).
"""
import os
from qgis.core import (
    QgsApplication, QgsProject, QgsRasterLayer, QgsVectorLayer,
    QgsCoordinateReferenceSystem, QgsFillSymbol, QgsRectangle,
    QgsReferencedRectangle,
)

REPO = r"C:\Users\Photogrammetry\AutomateSuSheetCreation"
DRONE = os.path.join(REPO, "GCP-Drone-Flight-2025.jpg")
SAM = os.path.join(REPO, "SAM_prototype", "sam_architecture_2025_overlap.gpkg")
HUMAN = os.path.join(REPO, "Architecture_2025.shp")
PROJ = os.path.join(REPO, "SAM_vs_Human_2025.qgs")

QgsApplication.setPrefixPath(r"C:\Program Files\QGIS 3.40.8", True)
qgs = QgsApplication([], False)
qgs.initQgis()

project = QgsProject.instance()
project.clear()
project.setCrs(QgsCoordinateReferenceSystem("EPSG:32632"))

# --- drone ortho (bottom) ---
drone = QgsRasterLayer(DRONE, "Drone ortho 2025")
if not drone.isValid():
    raise RuntimeError("drone layer invalid: " + DRONE)
project.addMapLayer(drone)

# --- human labelled architecture (cyan outline) ---
human = QgsVectorLayer(HUMAN, "Architecture 2025 (human)", "ogr")
if not human.isValid():
    raise RuntimeError("human layer invalid: " + HUMAN)
human.renderer().setSymbol(QgsFillSymbol.createSimple(
    {"color": "0,0,0,0", "outline_color": "0,255,255,255", "outline_width": "0.25"}))
project.addMapLayer(human)

# --- SAM predicted architecture (red outline) ---
sam = QgsVectorLayer(SAM, "SAM predicted 2025 (overlap+dedup)", "ogr")
if not sam.isValid():
    raise RuntimeError("SAM layer invalid: " + SAM)
sam.renderer().setSymbol(QgsFillSymbol.createSimple(
    {"color": "0,0,0,0", "outline_color": "255,0,0,255", "outline_width": "0.25"}))
project.addMapLayer(sam)

# zoom the saved view to the architecture extent
try:
    ext = human.extent()
    ext.scale(1.1)
    project.viewSettings().setDefaultViewExtent(
        QgsReferencedRectangle(ext, QgsCoordinateReferenceSystem("EPSG:32632")))
except Exception as e:
    print("view-extent set skipped:", e)

project.write(PROJ)
print("WROTE_PROJECT", PROJ)
qgs.exitQgis()
