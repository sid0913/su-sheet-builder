

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
from qgis.core import QgsApplication, QgsProject, QgsVectorLayer
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
    """Adds a vector layer to the QGIS project."""
    print(f"Adding layer {name}...")
    vlayer = QgsVectorLayer(uri, name, "ogr")
    project.addMapLayer(vlayer)
    group.insertLayer(0, vlayer)  # Insert the layer at the top of the group
    print("Layer added:", vlayer.name())


def clipRaster( input_raster, mask_layer, output_path):
    # Set parameters for the clip operation
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


SU = "SU_17001"  # Example SU name, change as needed
TRENCH = "Trench "+SU[-5:-3]+"000"  # Extract trench number from SU name
JobID = "707"
SU_ShapeFile = "3D_SU_Shapefiles/SU_17001_EPSG_32632.shp"  # Example shapefile name, change as needed
DEM_path = "DEM/Pgram_Job_707_SU17001_dem.tif"

# Get the project instance
project = QgsProject.instance()
# # Print the current project file name (might be empty in case no projects have been loaded)
# print(project.fileName()) #doesn't print even with the older version of QGIS


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



addLayer(SU_ShapeFile,"SU_17001_EPSG_32632.shp",SU_folder)
#add the layer to the SU folder



print("clipping DEM to the mask layer...")
# Print the trench folder name
#clip DEM to the mask layer
clipRaster(
    input_raster=DEM_path,
    mask_layer=SU_ShapeFile,
    output_path=SU+"_DEM.tif"
)



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



