

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
from qgis.core import QgsApplication, QgsLayoutExporter, QgsReadWriteContext, QgsProject, QgsPrintLayout, QgsVectorLayer, QgsRasterLayer, QgsRasterShader, QgsColorRampShader, QgsSingleBandPseudoColorRenderer, QgsStyle, QgsProject
from PyQt5.QtXml import QDomDocument
import processing
from processing.core.Processing import Processing
# Supply path to qgis install location
QgsApplication.setPrefixPath("C:\\Program Files\\QGIS 3.40.8", True)  


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
    return vlayer

def lockItem(item):
    """Locks the specified item in the layout."""
    if item:
        item.setLocked(True)
        item.setKeepLayerSet(True)  # Locks the layers in the map item
        item.setKeepLayerStyles(True)  # Locks the layer styles in the map item
        # item.setExtent(True)  # Locks the map item's extent
        
        print(f"Item {item.displayName()} locked.")
    else:
        print("Item is None, cannot lock.")


def unlockItem(item):
    """Unlocks the specified item in the layout."""
    if item:
        
        item.setKeepLayerSet(False)  # Unlocks the layers in the map item
        item.setKeepLayerStyles(False)  # Unlocks the layer styles in the map item
        # item.setExtent(False)  # Unlocks the map item's extent
        item.setLocked(False)
        print(f"Item {item.displayName()} unlocked.")
    else:
        print("Item is None, cannot unlock.")

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
        'SHAPE_RESTORE_SHX': "YES",  # Ensure SHX file is created
    }

    # Run the contour generation
    processing.run("gdal:contour", contour_params)

    print(f"Contours generated successfully and saved to {output_path}")
    return output_path

def addContour(contour_file, group):
    """Adds contour layer to the specified group in the project.
    Args:
        contour_file (str): Path to the contour shapefile.
        group (QgsLayerTreeGroup): The group to add the contour layer to.
    Returns:
        QgsVectorLayer: The added contour layer."""
    print(f"Adding contour layer from {contour_file}...")
    contour_layer = QgsVectorLayer(contour_file, "Contours", "ogr")
    if not contour_layer.isValid():
        print("Failed to load contour layer.")
        return
    
    
    
    # group.insertLayer(0, contour_layer)  # Insert the layer at the top of the group

    #add contour style

    # style = QgsStyle.defaultStyle()
    # style.readFromQML("contour_style.qml")
    # contour_layer.renderer().readXML(style.symbol('default_symbol'))
    
    contour_layer.loadNamedStyle('contour_style.qml')
    contour_layer.triggerRepaint()
    project.addMapLayer(contour_layer)
    


    print("Contour layer added:", contour_layer.name())
    return contour_layer

def addDEM(DEM_path, group):
    """Adds a DEM layer to the specified group in the project.
    Args:
        DEM_path (str): Path to the DEM file.   
        group (QgsLayerTreeGroup): The group to add the DEM layer to.
    Returns:
        QgsRasterLayer: The added DEM layer."""
    print(f"Adding DEM layer from {DEM_path}...")
    dem_layer = QgsRasterLayer(DEM_path, "DEM Layer")
    if not dem_layer.isValid():
        print("Failed to load DEM layer.")
        return
    
    
    # group.insertLayer(0, dem_layer)  # Insert the layer at the top of the group
    
    # Set the style for the DEM layer
    # dem_layer.loadNamedStyle('DEM_Color_Ramp_Syle.qml')
    project.addMapLayer(dem_layer)
    # dem_layer.reload()
    # dem_layer.triggerRepaint()
    # dem_layer.repaintRequested.emit()

    # force_style_refresh(dem_layer)
    # dem_layer.dataChanged.emit()

    #add a default color ramp shader to the DEM layer
    color_ramp = QgsStyle().defaultStyle().colorRamp('Viridis')
    ramp_shader = QgsColorRampShader(4.5, 4.8, color_ramp)
    ramp_shader.classifyColorRamp()# Add this line
    raster_shader = QgsRasterShader()
    raster_shader.setRasterShaderFunction(ramp_shader)

    renderer = QgsSingleBandPseudoColorRenderer(dem_layer.dataProvider(), 1, raster_shader)

    dem_layer.setRenderer(renderer)
    dem_layer.triggerRepaint()
    
    # Method 5: For vector layers, trigger feature count update
    # if hasattr(dem_layer, 'updateFeatureCount'):
    #     dem_layer.updateFeatureCount()


    

    print("DEM layer added:", dem_layer.name())
    return dem_layer



class SUSheet():
    def __init__(self, template_path:str, su:str, trench:str, description:str, pdf_path:str, layers_dict:dict):
        
        #initialize the SU information

        self.pdf_path = pdf_path
        self.su_info = {
            "su": su,  # SU name,
            "trench": trench,  # Trench name
            "description": description,  # Description of the SU,
        }

        self.layers_dict = layers_dict  # Dictionary of layers to be added to the layout


        #load the layout template
        self.doc, self.layout, self.items_dict, self.template_map_content_dict = self.load_layout_template(template_path)


        self.title = self.items_dict['Trench 17000 • SU 17001']["obj"]
        self.description = self.items_dict['Description:']["obj"]

        self.title.setText(f"{self.su_info['trench']} • {self.su_info['su']}")
        self.description.setText(self.su_info['description'])

        #manipulate the zoom level of the layout
        # self.items_dict['Map'].setScale(1000)  # Set the scale of

        print("maps", self.template_map_content_dict)

        self.maps = {
            "Page 1": {
                "DEM": self.template_map_content_dict['DEM Page 1'],
                "Ortho": self.template_map_content_dict['Ortho Page 1'],
                "Overview": self.template_map_content_dict['Overview Page 1'],
            },
            "Page 2": {
                "Overview": self.template_map_content_dict['Overview Page 2'],
            },
            "Page 3": {
                "Ortho": self.template_map_content_dict['Ortho Map Page 3'],
            },
            "Page 4": {
                "DEM": self.template_map_content_dict['DEM Page 4'],
            }
        }



        #TODO: pick the bookmark zoom level for the Trench

        #DEM map

        #TODO: turn on trench boundaries
        #TODO: turn on Trench Area contours
        # self.layers_dict["dem_layer"].setOpacity(0)  # Set the opacity of the DEM layer
        # self.layers_dict["contour_layer"].setItemVisibilityChecked(False)  # make the contour layer invisible in the layout
        # self.layers_dict["SU_ShapeFile"].setOpacity(0) 
        
        #TODO:zoom to the SU (try using zoom to layer somehow(?)- it seems to calculate the centroid already and can zoom out a bit if needed)
        #lock the DEM map item

        #overview map
        #TODO:zoom adjust
        #lock the overview map item

        #ortho map
        #TODO:zoom adjust
        #lock the ortho map item

        #TODO: adjust the legends on the maps


    
    
    def load_layout_template(self, template_path):
        """
        Loads a QGIS layout template.

        Args:
            template_path (str): The path to the .qpt template file.
        """
        print(f"Loading layout template from {template_path}...")
        project = QgsProject.instance()
        layout_name = os.path.splitext(os.path.basename(template_path))[0]
        layout = QgsPrintLayout(project)
        layout.initializeDefaults()  # Initialize with a default page
        layout.setName(layout_name)

        # Load the template content
        with open(template_path, 'rt', encoding='utf-8') as f:
            template_content = f.read()

        doc = QDomDocument()
        doc.setContent(template_content)
        items, ok = layout.loadFromTemplate(doc, QgsReadWriteContext(), True)

        # Check if the template was loaded successfully
        if not ok:
            print(f"Failed to load layout template from {template_path}.")
            return None, None, None

        print(f"Layout '{layout_name}' loaded successfully with {len(items)} items.")


        print("Setting up layout properties...")

        # print([( item.uuid(), item.displayName(), type(item).__name__) for item in items if type(item).__name__ == "QgsLayoutItemMap"])
        maps = [(item.displayName(), item) for item in items if type(item).__name__ == "QgsLayoutItemMap"]
        items = [( item.displayName(), {"id":item.uuid(), "obj":item, "type": type(item).__name__}) for item in items]
        items_dict = dict(items)  # Convert to a dictionary for easier access
        maps_dict = dict(maps)  # Convert to a dictionary for easier access
        
        # return layout properties
        return doc, layout, items_dict, maps_dict
    
    
    def generatePDF(self, pdf_path):
        """        Exports the layout to a PDF file.
        Args:
            pdf_path (str): The path where the PDF will be saved.
        """
        print("exporting layout to pdf...")

        if not self.layout:
            print("Layout is not initialized. Cannot export to PDF.")
            return
        
        if not pdf_path:

            # If no PDF path is provided and no default path is set, print an error message
            if not self.pdf_path:
                print("No PDF path provided. Cannot export to PDF.")
                return
            
            #use the default pdf path
            else:
                pdf_path = self.pdf_path
        
        print("The layers at this time are:")
        print(self.layers_dict)

        print("The items in the layout are and their locked values:")
        print([ (obj["obj"].displayName(), obj["obj"].isLocked()) for obj in list(self.items_dict.values()) if obj["obj"].isLocked()])

        #export the layout to PDF
        exporter = QgsLayoutExporter(self.layout)
        exporter.exportToPdf(pdf_path, QgsLayoutExporter.PdfExportSettings())

# QGS_FILE_NAME="TARP_2025_SU_Template_new_test.qgs"

# QGS_FILE_NAME="TARP_SU_Sheets_2025_test.qgs"
QGS_FILE_NAME="TARP_SU_Sheets_2025_test_updating.qgs"

SU = "SU_17001"  # Example SU name, change as needed
TRENCH = "Trench "+SU[-5:-3]+"000"  # Extract trench number from SU name
JobID = "707"
SU_ShapeFile_name = "SU_17001_EPSG_32632.shp"
SU_ShapeFile = os.path.join("3D_SU_Shapefiles",SU_ShapeFile_name)  # Example shapefile name, change as needed
DEM_path = os.path.join("DEM","Pgram_Job_707_SU17001_dem.tif")
CONTOUR_INTERVAL = 0.02
TEMPLATE_PDF_PATH = "new_layout.pdf"  # Path to the template PDF file, change as needed



layers_dict = {}



SU_data = {
    "SU": SU,
    "TRENCH": TRENCH,
    "JobID": JobID,
    "description": "SU 17001 description specific",  # Add a description for the SU
    "SU_ShapeFile_name": SU_ShapeFile_name,
    "SU_ShapeFile": SU_ShapeFile,
    "DEM_path": DEM_path,
}

# Get the project instance
project = QgsProject.instance()

if not os.path.exists(QGS_FILE_NAME):
    raise FileNotFoundError(f"Project file {QGS_FILE_NAME} not found. Please check the file path.")

print("Loading project...")
project.read(QGS_FILE_NAME)  # Load the project file
print("project",project.fileName())







#adding it to the right trench and SU folder
#create SU folder if it doesn't exist
root = project.layerTreeRoot()
print("These are the initial project layers",[item.name() for item in root.children()])

layers_dict["root"] = root  # Store the root in the dictionary

list_of_gcp_layers = [ item for item in root.children() if item.name() == "GCP-Drone-Flight-2025"]  # Get the root children (top-level groups and layers)
# check if the GCP-Drone-Flight-2025 layer exists
if len(list_of_gcp_layers) < 1:
    raise ValueError("GCP-Drone-Flight-2025 layer not found in the project. Please check the project structure.")
layers_dict["drone-flight"] = list_of_gcp_layers[0].layer()  # Store the GCP layer in the dictionary



trench_folder = root.findGroup(TRENCH)

SU_folder = trench_folder.findGroup(SU)
if SU_folder is None:
    print(f"Creating folder for {SU} under {TRENCH}...")
    SU_folder = trench_folder.addGroup(SU)  # Add SU folder under trench folder


# Check if the SU Shape layer already exists in the SU folder
# if project.mapLayersByName(SU_ShapeFile_name) is None:
#     #add the layer to the SU folder
print("Adding SU shapefile layer...")
su_shape_layer = addLayer(SU_ShapeFile,SU_ShapeFile_name,SU_folder)
layers_dict["SU_ShapeFile"] = su_shape_layer  # Store the layer in the dictionary



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



dem_layer = addDEM(SU+"_DEM.tif", SU_folder)
layers_dict["dem_layer"] =  dem_layer # Store the layer in the dictionary

#add the contour layer to the SU folder
contour_layer = addContour(contour_file, SU_folder)
layers_dict["contour_layer"] =  contour_layer # Store the layer in the dictionary

#create an SU Sheet
su_sheet = SUSheet("SU_Layout_Templates/SU_Template_17000.qpt", SU, TRENCH, SU_data["description"], TEMPLATE_PDF_PATH, layers_dict)

#manipulate the layout items
print("Manipulating layout items...")


#generate the SU Sheet PDF
su_sheet.generatePDF(TEMPLATE_PDF_PATH)  # Generate the PDF using the template




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


