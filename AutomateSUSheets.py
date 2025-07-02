
# working with QGIS in Python that can add layers


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
from qgis.core import QgsApplication, QgsProject
# from qgis import processing

# import processing
from processing.core.Processing import Processing



# # Supply path to qgis install location
QgsApplication.setPrefixPath("C:\\Program Files\\QGIS 3.40.8", True)  
from qgis.core import QgsProject


PATH = "C:\\Users\\Photogrammetry"

qgs = QgsApplication([], False)


print("Intializing QGIS Application...")
# Load providers
qgs.initQgis()



# Get the project instance
project = QgsProject.instance()
# # Print the current project file name (might be empty in case no projects have been loaded)
# print(project.fileName()) #doesn't print even with the older version of QGIS


print("Loading project...")
project.read('TARP_SU_Sheets_2025_test_updating_v2.qgs')
print("project",project.fileName())

# print("Adding layers...")
# uri = "TARP 2025 Trench Boundaries 6-1-2025.shp"
# vlayer = QgsVectorLayer(uri, "TARP 2025 Trench Boundaries 6-1-2025", "ogr")
# QgsProject.instance().addMapLayer(vlayer)
# print("Layer added:", layer.name())

SU_number = "SU_17004"
Processing.initialize()





# processing.initialize(QgsApplication.processingRegistry())
# run the script
import processing



# Path to your custom script file
script_path = "obj2shp.py"

# Make sure the script exists
if not os.path.exists(script_path):
    raise FileNotFoundError(f"Script not found: {script_path}")

# Get the script provider and add the script manually
# script_provider = QgsApplication.processingRegistry().providerById('script')
# script_provider.loadAlgorithms()  # make sure existing ones are loaded
# script_provider.loadAlgorithm(script_path)


print("Available processing algorithms:")
for alg in QgsApplication.processingRegistry().algorithms():
    # print(alg.id(), "->", alg.displayName())
    if 'Convert' in alg.id() or "Convert" in alg.displayName():
        print("Script found:", alg.id(), "->", alg.displayName())

parameters = {
    "obj_file": "C:\\Users\\Photogrammetry\\Volumetrics_2025\\Trench 17000\\SU_17004.obj",
    "output_file_path": "3D_SU_Shapefiles",
    "su_number": 17004,
    "year": "2025"
}

from generate_top_shp import create_SU_shp_file
create_SU_shp_file(parameters)

# print("Running processing algorithm...")
# result = processing.run("script:Convert SU 3D OBJ to 3D SHP Polygon",{
#     "obj_file": os.path.join(PATH, "Volumetrics_2025","Trench 17000", SU_number),   
#     "output_file_path": os.path.join(PATH, "AutomateRockMask", "3D_SU_Shapefiles"),
#     "su_number": SU_number,
#     "year": "2025",
# })

# print("Processing result:", result)

#UNCOMMENT TO SAVE THE PROJECT
# print("saving project...")
# project.write()  # Save the project after adding the layer

# Write your code here to load some layers, use processing
# algorithms, etc.

# Finally, exitQgis() is called to remove the
# provider and layer registries from memory
print("Exiting QGIS Application...")
qgs.exitQgis()  








# # # Load another project

# print(os.listdir(project.absoluteFilePath()))



