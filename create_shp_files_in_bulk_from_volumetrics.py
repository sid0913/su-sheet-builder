import sys
sys.path = ['', 'C:\\PROGRA~1\\QGIS34~1.8\\apps\\qgis-ltr\\python', 'C:\\Program Files\\QGIS 3.40.8\\bin', 'C:\\Program Files\\QGIS 3.40.8\\bin\\python312.zip', 'C:\\PROGRA~1\\QGIS34~1.8\\apps\\Python312\\DLLs', 'C:\\PROGRA~1\\QGIS34~1.8\\apps\\Python312\\Lib', 'C:\\PROGRA~1\\QGIS34~1.8\\apps\\Python312', 'C:\\PROGRA~1\\QGIS34~1.8\\apps\\Python312\\Lib\\site-packages', 'C:\\PROGRA~1\\QGIS34~1.8\\apps\\Python312\\Lib\\site-packages\\win32', 'C:\\PROGRA~1\\QGIS34~1.8\\apps\\Python312\\Lib\\site-packages\\win32\\lib', 'C:\\PROGRA~1\\QGIS34~1.8\\apps\\Python312\\Lib\\site-packages\\Pythonwin']
sys.path.append("C:\\Program Files\\QGIS 3.40.8\\apps\\qgis-ltr\\python\\plugins")
import pytz
from datetime import datetime
import os
from generate_top_shp import create_SU_shp_file
from qgis.core import QgsApplication
from processing.core.Processing import Processing
import time

#this is where QGS is installed
QGS_PROGRAM_PATH = "C:\\Program Files\\QGIS 3.40.8"

def start_QGS():
    """Initializes the QGIS application and sets up the environment."""
    # Supply path to qgis install location
    QgsApplication.setPrefixPath(QGS_PROGRAM_PATH, True) 

    # Initialize QGIS Application
    qgs = QgsApplication([], False)
    print("Intializing QGIS Application...")
    # Load providers
    qgs.initQgis()
    Processing.initialize()  # Initialize the Processing framework

    return qgs

def close_QGS(qgs):
    """Exits the QGIS application."""
    print("Exiting QGIS Application...")
    qgs.exitQgis()





PATH = "C:\\Users\\Photogrammetry"
YEAR = 2025

# TOTAL_ITEMS = len(os.listdir(os.path.join(PATH, "Volumetrics_2025", "SU Top OBJs"))) + len(os.listdir(os.path.join(PATH, "Volumetrics_2025", "Trench 18000"))) + len(os.listdir(os.path.join(PATH, "Volumetrics_2025", "Trench 19000"))) 
TOTAL_ITEMS = len(os.listdir(os.path.join(PATH, "Volumetrics_2025", "SU Top OBJs"))) 
items_processed = len([f for f in os.listdir(os.path.join(PATH, "GIS_2025", "3D_SU_Shapefiles")) if f.endswith(".shp")]) // 2
print(f"Total items to process: {TOTAL_ITEMS}")
print(f"Total items already processed: {items_processed}")


qgs = start_QGS()
print("QGIS Application started successfully.")

try:
    for su_obj in os.listdir(os.path.join(PATH, "Volumetrics_2025", "SU Top OBJs")):
        if su_obj.endswith(".obj") and su_obj.startswith("SU_"):
            file_path = os.path.join(PATH, "Volumetrics_2025", "SU Top OBJs", su_obj)

            su_num = su_obj.split('.')[0].split('_')[-2]

            #check if the output file exists
            output_file_path = os.path.join(PATH, "GIS_2025", "3D_SU_Shapefiles", f"SU_{su_num}_EPSG_32632.shp")
            if os.path.exists(output_file_path):    
                continue  # Skip if the shapefile already exists
            
            if not os.path.exists(file_path):
                print(f"ERROR: File {file_path} does not exist, skipping...")
                continue

            try:
                start = time.time()  # Start time for performance measurement
                create_SU_shp_file({
                    "obj_file": file_path,
                    "output_file_path": os.path.join(PATH, "GIS_2025", "3D_SU_Shapefiles"),
                    "su_number": int(su_num),
                    "year": YEAR
                })
                time_elapsed = round((time.time() - start) / 60, 3)  # Calculate time elapsed in minutes
                print(f"SU shapefile created in {time_elapsed} minutes for {su_obj}.")
                items_processed += 1
                percentage_complete = (items_processed / TOTAL_ITEMS) * 100
                print(f"Processed {items_processed}/{TOTAL_ITEMS}: {su_obj}")
                print(f"Processed {su_obj}... {percentage_complete:.2f}% complete")
            except Exception as e:
                print(f"Error processing {su_obj}: {e}")
                # Log the error to a file
                with open(os.path.join(PATH, "AutomateRockMask", "shp_error_log.txt"), "a") as error_file:
                    error_file.write(f"{datetime.now(pytz.timezone('Europe/Rome')).strftime("%Y-%m-%d %H:%M:%S")} -- Error processing {su_obj}: {e}\n")
                continue

        else:
            continue

    print()
    print("All items processed successfully in!")
    print(f"Processed {items_processed} items out of {TOTAL_ITEMS}.")

finally:
    close_QGS(qgs)
    print("QGIS Application closed successfully.")