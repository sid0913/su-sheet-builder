# import sys

# print(sys.path)

# import sys
# import os

# # Adjust to your QGIS version and installation path
# qgis_path = "C:\\Program Files\\QGIS 3.36.2"
# python_path = os.path.join(qgis_path, 'python')
# plugin_path = os.path.join(qgis_path, 'python', 'plugins')

# sys.path.append(python_path)
# sys.path.append(plugin_path)

# # Set environment variables
# os.environ['QGIS_PREFIX_PATH'] = qgis_path
# os.environ['PATH'] += ';' + os.path.join(qgis_path, 'bin')

# print("Python Path:", sys.path)

# import qgis

import sys
sys.path.append("C:\\Program Files\\QGIS 3.36.2\\apps\qgis\\python")

from qgis.core import *
# # Supply path to qgis install location
QgsApplication.setPrefixPath("C:\\Program Files\\QGIS 3.36.2", True)  
# from qgis.core import QgsProject


# # Get the project instance
project = QgsProject.instance()
# Print the current project file name (might be empty in case no projects have been loaded)
# print(project.fileName())

# # Load another project
project.read('TARP_2025_SU_Template.qgs')
print(project.fileName())

