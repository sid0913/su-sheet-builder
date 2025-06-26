

import sys

# version = "3.36.2"  # Change this to your desired QGIS version
# version = "3.40.8"  # Change this to your desired QGIS version

# changes = {
#     "3.36.2": {
#         "install_path":"C:\\Program Files\\QGIS 3.36.2\\apps\\qgis\\python",
#         "prefix_path": "C:\\Program Files\\QGIS 3.36.2",
#     },
#     "3.40.8": {
#         "install_path":"C:\\Program Files\\QGIS 3.40.8\\apps\\qgis-ltr\\python",
#         "prefix_path": "C:\\Program Files\\QGIS 3.40.8",
#     }
# }
import sys
# sys.path = [x for x in sys.path if 'Python312' not in x]  # Remove existing QGIS paths
# sys.path.insert(0, "C:\\Program Files\\QGIS 3.40.8\\apps\\Python312\\DLLs") # issues with DLL
# sys.path.insert(0, "C:\\Program Files\\QGIS 3.40.8\\apps\\Python312") # issues with DLL
# sys.path.insert(0, "C:\\Program Files\\QGIS 3.40.8\\apps\\qgis-ltr\\python") # issues with DLL
# print(sys.path)

#got the sys.path result of qgis's python-qgis-ltr.bat file (this is a python console)
sys.path = ['', 'C:\\PROGRA~1\\QGIS34~1.8\\apps\\qgis-ltr\\python', 'C:\\Program Files\\QGIS 3.40.8\\bin', 'C:\\Program Files\\QGIS 3.40.8\\bin\\python312.zip', 'C:\\PROGRA~1\\QGIS34~1.8\\apps\\Python312\\DLLs', 'C:\\PROGRA~1\\QGIS34~1.8\\apps\\Python312\\Lib', 'C:\\PROGRA~1\\QGIS34~1.8\\apps\\Python312', 'C:\\PROGRA~1\\QGIS34~1.8\\apps\\Python312\\Lib\\site-packages', 'C:\\PROGRA~1\\QGIS34~1.8\\apps\\Python312\\Lib\\site-packages\\win32', 'C:\\PROGRA~1\\QGIS34~1.8\\apps\\Python312\\Lib\\site-packages\\win32\\lib', 'C:\\PROGRA~1\\QGIS34~1.8\\apps\\Python312\\Lib\\site-packages\\Pythonwin']
sys.path.append("C:\\Program Files\\QGIS 3.40.8\\apps\\qgis-ltr\\python\\plugins")


import os
from qgis.core import QgsApplication, QgsProject, QgsVectorLayer, QgsRasterLayer
# from qgis import processing

import processing
from processing.core.Processing import Processing



# # Supply path to qgis install location
QgsApplication.setPrefixPath("C:\\Program Files\\QGIS 3.40.8", True)  
from qgis.core import QgsProject


PATH = "C:\\Users\\Photogrammetry"

qgs = QgsApplication([], False)


print("Intializing QGIS Application...")
# Load providers
qgs.initQgis()
Processing.initialize()  # Initialize the Processing framework

#helper functions
def addLayer(uri, name, group):
    """Adds a Map layer to the QGIS project."""
    print(f"Adding layer {name}...")
    vlayer = QgsVectorLayer(uri, name, "ogr")
    project.addMapLayer(vlayer)
    # group.insertLayer(0, vlayer)  # Insert the layer at the top of the group
    print("Layer added:", vlayer.name())


def clipRaster( input_raster, mask_layer, output_path):
    # Set parameters for the clip operation and save the output (without adding the layer to the project)
    clip_params = {
        'INPUT': input_raster,
        'MASK': mask_layer,
        'KEEP_RESOLUTION': True, # Optional: Set to True to maintain input raster's resolution
        'OPTIONS': '', # Optional: Specify GDAL options if needed
        'OUTPUT': output_path
    }

    # Run the clip operation
    processing.run("gdal:cliprasterbymasklayer", clip_params)

    print(f"Raster clipped successfully to {output_path}")

def get_contours(input_raster, SU, interval=0.02):
    """Generates contours from a raster layer."""

    print(f"Generating contours for {SU} with interval {interval*100} cm...")
    output_path = f"{SU}_{int(interval*100)}cm.shp"  # Output shapefile for contours
    contour_params = {
        'INPUT': input_raster,
        'BAND': 1,  # Assuming the first band is the one to contour
        'INTERVAL': interval,
        'FIELD_NAME': 'ELEV',  # Name of the field to store contour values
        'OUTPUT': output_path,
        'SHAPE_RESTORE_SHX': True,  # Ensure SHX file is created
    }

    # Run the contour generation
    processing.run("gdal:contour", contour_params)

    print(f"Contours generated successfully and saved to {output_path}")
    return output_path

def addContour(contour_file, group):
    """Adds contour layer to the specified group in the project."""
    print(f"Adding contour layer from {contour_file}...")
    contour_layer = QgsVectorLayer(contour_file, "Contours", "ogr")
    if not contour_layer.isValid():
        print("Failed to load contour layer.")
        return
    
    
    project.addMapLayer(contour_layer)
    # group.insertLayer(0, contour_layer)  # Insert the layer at the top of the group

    #add contour style

    # style = QgsStyle.defaultStyle()
    # style.readFromQML("contour_style.qml")
    # contour_layer.renderer().readXML(style.symbol('default_symbol'))
    
    contour_layer.loadNamedStyle('contour_style.qml')
    contour_layer.triggerRepaint()


    print("Contour layer added:", contour_layer.name())

def addDEM(DEM_path, group):
    """Adds a DEM layer to the specified group in the project."""
    print(f"Adding DEM layer from {DEM_path}...")
    dem_layer = QgsRasterLayer(DEM_path, "DEM Layer")
    if not dem_layer.isValid():
        print("Failed to load DEM layer.")
        return
    
    project.addMapLayer(dem_layer)
    # group.insertLayer(0, dem_layer)  # Insert the layer at the top of the group

    # Set the style for the DEM layer
    dem_layer.loadNamedStyle('DEM_Color_Ramp_Syle.qml')
    dem_layer.triggerRepaint()

    print("DEM layer added:", dem_layer.name())


SU = "SU_17001"  # Example SU name, change as needed
TRENCH = "Trench "+SU[-5:-3]+"000"  # Extract trench number from SU name
JobID = "707"
SU_ShapeFile_name = "SU_17001_EPSG_32632.shp"
SU_ShapeFile = os.path.join("3D_SU_Shapefiles",SU_ShapeFile_name)  # Example shapefile name, change as needed
DEM_path = os.path.join("DEM","Pgram_Job_707_SU17001_dem.tif")
CONTOUR_INTERVAL = 0.02


# Get the project instance
project = QgsProject.instance()


print("Loading project...")
project.read('TARP_SU_Sheets_2025_test.qgs')
print("project",project.fileName())







#adding it to the right trench and SU folder
#create SU folder if it doesn't exist
root = project.layerTreeRoot()
trench_folder = root.findGroup(TRENCH)

SU_folder = trench_folder.findGroup(SU)
if SU_folder is None:
    print(f"Creating folder for {SU} under {TRENCH}...")
    SU_folder = trench_folder.addGroup(SU)  # Add SU folder under trench folder


# Check if the SU Shape layer already exists in the SU folder
# if project.mapLayersByName(SU_ShapeFile_name) is None:
#     #add the layer to the SU folder
print("Adding SU shapefile layer...")
addLayer(SU_ShapeFile,SU_ShapeFile_name,SU_folder)




# # print("clipping DEM to the mask layer...")
# # Print the trench folder name
# #clip DEM to the mask layer
clipRaster(
    input_raster=DEM_path,
    mask_layer=SU_ShapeFile,
    output_path=SU+"_DEM.tif"
)

#get contours from the clipped DEM
contour_file = get_contours(SU+"_DEM.tif", SU, interval=CONTOUR_INTERVAL)
print("Contour file generated:", contour_file)
addContour(contour_file, SU_folder)


addDEM(SU+"_DEM.tif", SU_folder)

#UNCOMMENT TO SAVE THE PROJECT
print("saving project...")
project.write()  # Save the project after adding the layer

# Write your code here to load some layers, use processing
# algorithms, etc.

# Finally, exitQgis() is called to remove the
# provider and layer registries from memory
print("Exiting QGIS Application...")
qgs.exitQgis()  








# # # Load another project

# print(os.listdir(project.absoluteFilePath()))



