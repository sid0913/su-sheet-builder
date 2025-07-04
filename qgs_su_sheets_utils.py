

import sys


#got the sys.path result of qgis's python-qgis-ltr.bat file (this is a python console)
import sys
sys.path = ['', 'C:\\PROGRA~1\\QGIS34~1.8\\apps\\qgis-ltr\\python', 'C:\\Program Files\\QGIS 3.40.8\\bin', 'C:\\Program Files\\QGIS 3.40.8\\bin\\python312.zip', 'C:\\PROGRA~1\\QGIS34~1.8\\apps\\Python312\\DLLs', 'C:\\PROGRA~1\\QGIS34~1.8\\apps\\Python312\\Lib', 'C:\\PROGRA~1\\QGIS34~1.8\\apps\\Python312', 'C:\\PROGRA~1\\QGIS34~1.8\\apps\\Python312\\Lib\\site-packages', 'C:\\PROGRA~1\\QGIS34~1.8\\apps\\Python312\\Lib\\site-packages\\win32', 'C:\\PROGRA~1\\QGIS34~1.8\\apps\\Python312\\Lib\\site-packages\\win32\\lib', 'C:\\PROGRA~1\\QGIS34~1.8\\apps\\Python312\\Lib\\site-packages\\Pythonwin']
sys.path.append("C:\\Program Files\\QGIS 3.40.8\\apps\\qgis-ltr\\python\\plugins")

import os
from qgis.core import QgsApplication, QgsRasterBandStats, QgsRasterRange, QgsRectangle, QgsLayoutItemScaleBar, QgsMapLayer, QgsLayoutItemMap, QgsLayoutExporter, QgsReadWriteContext, QgsProject, QgsPrintLayout, QgsVectorLayer, QgsRasterLayer, QgsRasterShader, QgsColorRampShader, QgsSingleBandPseudoColorRenderer, QgsStyle, QgsProject
from PyQt5.QtXml import QDomDocument
from PyQt5.QtGui import QFont
import processing
from processing.core.Processing import Processing
from generate_top_shp import create_SU_shp_file




#function to set up QGIS file by deleting existing layers and adding a drone flight layer
def setupQGISFile(project, layers_dict):


    
    
    print("Clear existing project layers...")
    # Get the list of all layers in the project
    layers = list(project.mapLayers().values())

    # Remove each layer
    for layer in layers:
        project.removeMapLayer(layer)

    print("Project cleared. Adding drone flight layer...")
    if not os.path.exists("GCP-Drone-Flight-2025.jpg"):
        raise FileNotFoundError("GCP-Drone-Flight-2025.jpg not found. Please check the file path.")
    drone_flight_layer = QgsRasterLayer("GCP-Drone-Flight-2025.jpg", "GCP-Drone-Flight-2025")
    layers_dict["drone-flight"] = drone_flight_layer  # Store the drone flight layer in the dictionary
    project.addMapLayer(drone_flight_layer)  # Add the drone flight layer to the project



#helper functions
def add_layer(uri, name, project):
    """Adds a Map layer to the QGIS project."""
    print(f"Adding layer {name}...")
    
    if not os.path.exists(uri):
        raise FileNotFoundError(f"Layer file {uri} not found. Please check the file path.")
    
    vlayer = QgsVectorLayer(uri, name, "ogr")
    project.addMapLayer(vlayer)
    print("Layer added:", vlayer.name())
    return vlayer


def setNoDataValue(layer):
    provider = layer.dataProvider()
    band_count = provider.bandCount()

    # Add 255 as additional no-data value for each band
    for band in range(1, band_count + 1):
        # Get existing no-data ranges
        existing_no_data = provider.userNoDataValues(band)

        # Check if 255 is already included
        already_set = any(r.min() == 255 and r.max() == 255 for r in existing_no_data)

        if not already_set:
            # Create a QgsRasterRange with 255 as min and max
            new_range = QgsRasterRange(255, 255)
            existing_no_data.append(new_range)

            # Set updated no-data ranges for the band
            provider.setUserNoDataValue(band, existing_no_data)

    layer.triggerRepaint()


def get_DEM_path(job_id):
    """Returns the path to the DEM file based on the job ID."""
    for file in os.listdir("DEM"):
        # Check if the file matches the job ID pattern
        if f"Pgram_Job_{job_id}" in file and file.endswith(".tif"):
            dem_path = os.path.join("DEM", file)
            print(f"Found DEM file: {dem_path}")
            return dem_path

    #if no DEM file is found, raise an error
    raise FileNotFoundError(f"DEM file for job_id {job_id} not found. Please check the DEM/ directory.")


def add_ortho_photo(job_id, project, layers_dict):
    """Adds an ortho photo layer to the project based on the job_id."""


    for file in os.listdir("Orthos"):

        #check if it is a jpg file and then split the filename by '_' and if the second index is matches the job ID, then add the layer
        if file.endswith(".jpg") and file.split('_')[2] == job_id:
            ortho_photo_path = os.path.join("Orthos", file)
            print("Adding ortho photo layer...")


            # Create a QgsRasterLayer for the ortho photo
            ortho_layer = QgsRasterLayer(ortho_photo_path, f"Ortho")
            # provider = ortho_layer.dataProvider()

            # result  = provider.setNoDataValue(1, 0) #first one is referred to band number

            # if result:
            #     print(f"NoData value set successfully for {ortho_layer.name()}")
            # else:
            #     print(f"Failed to set NoData value for {ortho_layer.name()}") 

            # ortho_layer.triggerRepaint()

            #get rid of the white space around the ortho photo
            setNoDataValue(ortho_layer)  # Set NoData value for the ortho layer

            project.addMapLayer(ortho_layer)
            # Add the ortho photo layer to the layers dictionary
            layers_dict["ortho_photo"] = ortho_layer
            return
        
    # If no ortho photo is found, raise an error
    raise FileNotFoundError(f"No ortho photo found for Job {job_id} in the 'Orthos' directory.")
    


def get_high_contrast_min_max_values(dem_layer, shader):
    """Calculates high contrast min/max values for a DEM layer using various methods. This helps create a high-contrast color ramp for the DEM layer.
    Args:
        dem_layer (QgsRasterLayer): The DEM layer to analyze.
        shader (QgsRasterShader): The raster shader for the DEM layer.
    Returns:
        tuple: A tuple containing the high contrast min and max values."""

    # Get the layer's data provider    
    provider = dem_layer.dataProvider()

    # Get cumulative cut values (2% - 98% range often used for contrast)
    # This is often what creates the "good contrast" you see
    band_stats = provider.bandStatistics(1, QgsRasterBandStats.All)
    
    # Calculate 2% and 98% cumulative cuts
    hist = provider.histogram(1, 100, band_stats.minimumValue, band_stats.maximumValue)
    
    if hist.valid:
        cumulative = []
        total = sum(hist.histogramVector)
        running_sum = 0
        
        for count in hist.histogramVector:
            running_sum += count
            cumulative.append(running_sum / total)
        
        # Calculate bin width manually
        bin_width = (hist.maximum - hist.minimum) / len(hist.histogramVector)
        
        # Find 2.5% and 95% cut points
        min_2_5_percent = None
        max_95_percent = None
        
        for i, cum_pct in enumerate(cumulative):
            if min_2_5_percent is None and cum_pct >= 0.025:
                min_2_5_percent = hist.minimum + (i * bin_width)
            if max_95_percent is None and cum_pct >= 0.95:
                max_95_percent = hist.minimum + (i * bin_width)
                break
        
        if min_2_5_percent is not None and max_95_percent is not None:
            # print(f"2.5%-95% stretch - Min: {min_2_5_percent}, Max: {max_95_percent}")
            return min_2_5_percent, max_95_percent
        else:
            raise ValueError("Failed to calculate 2.5% and 95% cut points from histogram data.")
    else:
        raise ValueError("Histogram data is not valid. Cannot calculate high contrast min/max values.")


def make_dem_color_ramp_high_contrast(dem_layer, min_elevation, max_elevation):
    """Creates a high-contrast color ramp for a DEM layer. This assigns the renderer a lower max elevation value to create a high-contrast color ramp.
    Args:
        dem_layer (QgsRasterLayer): The DEM layer to apply the color ramp to.
    Returns:
        QgsSingleBandPseudoColorRenderer: The renderer with the high-contrast color ramp applied."""
    

    #add a default color ramp shader to the DEM layer
    color_ramp = QgsStyle().defaultStyle().colorRamp('RdYlBu')
    color_ramp.invert()  # Invert the color ramp to have lower elevations in blue and higher in red


    renderer = dem_layer.renderer()
    provider = dem_layer.dataProvider()
    extent = dem_layer.extent()

    ver = provider.hasStatistics(1, QgsRasterBandStats.All)

    stats = provider.bandStatistics(1, QgsRasterBandStats.All,extent, 0)

    if ver is not False:
        print ("minimumValue = ", stats.minimumValue)

        print ("maximumValue = ", stats.maximumValue)

    if (stats.minimumValue < 0):
        min = 0  

    else: 
        min= stats.minimumValue
    
    
    ramp_shader = QgsColorRampShader(min_elevation, max_elevation, color_ramp)
    ramp_shader.classifyColorRamp()# Add this line
    raster_shader = QgsRasterShader()
    raster_shader.setRasterShaderFunction(ramp_shader)
    renderer = QgsSingleBandPseudoColorRenderer(dem_layer.dataProvider(), 1, raster_shader)


    dem_layer.setRenderer(renderer)
    dem_layer.triggerRepaint()

    #makes the gradient high contrast by taking the 95% of the range to leave out the high elevations
    contrast_min_value, contrast_max_value = get_high_contrast_min_max_values(dem_layer, raster_shader)  # Get high contrast min/max values





    #use the new min and max values to create a new color ramp shader
    new_color_ramp = QgsStyle().defaultStyle().colorRamp('RdYlBu')
    new_color_ramp.invert()  # Invert the color ramp to have lower elevations in blue and higher in red
    new_ramp_shader = QgsColorRampShader(contrast_min_value, contrast_max_value, new_color_ramp)
    new_ramp_shader.classifyColorRamp()# Add this line
    new_raster_shader = QgsRasterShader()
    new_raster_shader.setRasterShaderFunction(new_ramp_shader)


    new_renderer = QgsSingleBandPseudoColorRenderer(dem_layer.dataProvider(), 1, new_raster_shader)
    # print (" classification minimumValue = ", new_renderer.classificationMin())
    # print (" classification maximumValue = ", new_renderer.classificationMax())

    #set the new dem layer settings
    dem_layer.setRenderer(new_renderer)
    dem_layer.triggerRepaint()



def lockItem(item):
    """Locks the specified item in the layout."""
    if item:
        #item.setLocked would have worked if we had figured out how to get the QgsLayoutItemMap object to uncheck/be invisible. Since we are using opacity, we use the following method

        item.setKeepLayerStyles(True)  # Keep the layer styles for the overview map item, page 1
        item.storeCurrentLayerStyles()  # Store the current layer set for the overview map item, page 1
        item.setFollowVisibilityPreset(False) #disable updates from project state
        
        print(f"Item {item.displayName()} locked.")
    else:
        print("Item is None, cannot lock.")

# def zoomToLayer(item, layer):
#     """Zooms the specified item to the extent of the given layer."""

#     if item and layer:
#         #zoom while keeping the layout item size the same 
#         item.setExtent(layer.extent())  # Set the extent of the overview map item to the layer's extent
#         print(f"Item {item.displayName()} zoomed to layer {layer.name()}.")
#     else:
#         print("Item or layer is None, cannot zoom.")


def zoomToLayerWithBufferAndScalebar(item: QgsLayoutItemMap, layer: QgsMapLayer,
                                     scalebar: QgsLayoutItemScaleBar,
                                     buffer_ratio: float = 0.2,
                                     scalebar_fraction: float = 0.5):
    """
    Zooms to a layer with buffer and sets the scale bar to occupy ~1/4 of map width (in mm).

    :param item: QgsLayoutItemMap
    :param layer: QgsMapLayer
    :param scalebar: QgsLayoutItemScaleBar
    :param buffer_ratio: Zoom-out buffer as fraction of layer width (e.g., 0.1 = 10%)
    :param scalebar_fraction: Desired visual width of scalebar as fraction of map item width (e.g., 0.25 = 1/4th)
    """

    if not item or not layer:
        print("Item or layer is None, cannot zoom.")
        return

    # Step 1: Zoom to buffered layer extent
    layer_extent = layer.extent()
    buffered_extent = layer_extent.buffered(layer_extent.width() * buffer_ratio)

    item_width_mm = item.rect().width()
    item_height_mm = item.rect().height()

    mu_per_mm_x = buffered_extent.width() / item_width_mm
    mu_per_mm_y = buffered_extent.height() / item_height_mm
    mu_per_mm = max(mu_per_mm_x, mu_per_mm_y)

    center = buffered_extent.center()
    new_width = item_width_mm * mu_per_mm
    new_height = item_height_mm * mu_per_mm

    new_extent = QgsRectangle(
        center.x() - new_width / 2,
        center.y() - new_height / 2,
        center.x() + new_width / 2,
        center.y() + new_height / 2
    )

    item.setExtent(new_extent)
    item.refresh()

    # Set scalebar width to 1/4 of map item width
    if scalebar:
        desired_width_mm = item_width_mm * scalebar_fraction
        scalebar.setLinkedMap(item)
        scalebar.setMinimumBarWidth(desired_width_mm)
        scalebar.update()

        print(f"Scalebar width set to {desired_width_mm:.2f} mm.")

    print(f"Map item '{item.displayName()}' zoomed to layer '{layer.name()}' with {int(buffer_ratio * 100)}% buffer.")

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

def get_contours(input_raster, su, interval=0.02):
    """Generates contours from a raster layer."""

    

    print(f"Generating contours for {su} with interval {interval*100} cm...")
    output_path = f"{su}_{int(interval*100)}cm.shp"  # Output shapefile for contours

    if os.path.exists(output_path):
        print(f"Contour file {output_path} already exists.")
        return output_path

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

def add_contour(contour_file, project):
    """Adds contour layer in the project.
    Args:
        contour_file (str): Path to the contour shapefile.
    Returns:
        QgsVectorLayer: The added contour layer."""
    print(f"Adding contour layer from {contour_file}...")
    contour_layer = QgsVectorLayer(contour_file, "Contours", "ogr")
    if not contour_layer.isValid():
        print("Failed to load contour layer.")
        return
    
    
    
    contour_layer.loadNamedStyle('Styles/contour_style.qml')
    contour_layer.triggerRepaint()
    project.addMapLayer(contour_layer)
    


    print("Contour layer added:", contour_layer.name())
    return contour_layer

def add_DEM(DEM_path, project):
    """Adds a DEM layer to the project.
    Args:
        DEM_path (str): Path to the DEM file.   
    Returns:
        QgsRasterLayer: The added DEM layer."""
    print(f"Adding DEM layer from {DEM_path}...")

    #this has the top 2D color gradient signifying the elevation
    dem_layer = QgsRasterLayer(DEM_path, "DEM Layer")

    #this has the top 3D volume-ish structure
    dem_lower_layer = QgsRasterLayer(DEM_path, "DEM Lower Layer")


    provider = dem_layer.dataProvider()
    
    # Get band statistics (band 1 for single-band DEM)
    stats = provider.bandStatistics(1, QgsRasterBandStats.All)
    
    min_elevation = round(stats.minimumValue, 2)
    max_elevation = round(stats.maximumValue, 2)

    elevation_stats = {
        "min_elevation": min_elevation,
        "max_elevation": max_elevation
    }

    #makes the color gradient high contrast
    make_dem_color_ramp_high_contrast(dem_layer, min_elevation, max_elevation)

    if not dem_layer.isValid() or not dem_lower_layer.isValid():
        print("Failed to load DEM layers.")
        return

    #add style to the lower DEM layer
    dem_lower_layer.loadNamedStyle("Styles/DEM_Hillshade_style_new.qml")

    #add them to the map
    project.addMapLayer(dem_lower_layer)
    project.addMapLayer(dem_layer)

    print("DEM layer added:", dem_layer.name())
    return dem_layer, dem_lower_layer, elevation_stats

#CITATION: https://stackoverflow.com/questions/8391411/how-to-block-calls-to-print
#prevents print statements from printing to the console
class HiddenPrints:
    def __enter__(self):
        self._original_stdout = sys.stdout
        sys.stdout = open(os.devnull, 'w')

    def __exit__(self, exc_type, exc_val, exc_tb):
        sys.stdout.close()
        sys.stdout = self._original_stdout

class SUSheet():
    def __init__(self, template_path:str, su:str, trench:str, description:str, pdf_path:str, elevation_stats, layers_dict:dict):
        
        #initialize the SU information

        self.pdf_path = pdf_path
        self.su_info = {
            "su": su,  # SU name,
            "trench": trench,  # Trench name
            "description": description,  # Description of the SU,
        }

        self.layers_dict = layers_dict  # Dictionary of layers to be added to the layout

        self.elevation_stats = elevation_stats  # Elevation statistics for the SU


        #load the layout template
        self.doc, self.layout, self.items_dict, self.template_map_content_dict = self.load_layout_template(template_path)
        # print("the items_dict is", self.items_dict.keys())
        # print("the items_dict is", [(self.items_dict[key]["obj"].displayName(), self.items_dict[key]["obj"]) for key in self.items_dict.keys()])

        #find the title and description items in the layout

        #find the placeholder text which differs by trench
        # e.g. "Trench 17000 • SU 17001" for Trench 17000's qgs template
        title_placeholder = ''
        for key in self.items_dict.keys():
            if f'{trench} • ' in key:
                title_placeholder = key
                break


        self.title = self.items_dict[title_placeholder]["obj"]
        self.description = self.items_dict['Description:']["obj"]

        self.title.setText(f"{self.su_info['trench']} • {self.su_info['su'].replace('_', ' ')}") # Replace underscores with spaces in the title
        self.description.setText(self.su_info['description']) 




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




        #Overview map
        print("Setting up Overview map item...")

        #TODO: turn on trench boundaries
        #TODO: turn on Trench Area contours
        self.layers_dict["drone-flight"].setOpacity(0)  # Set the opacity of the DEM layer
        self.layers_dict["dem_layer"].setOpacity(0)  # Set the opacity of the DEM layer
        self.layers_dict["contour_layer"].setOpacity(0)  # make the contour layer invisible in the layout
        self.layers_dict["ortho_photo"].setOpacity(0)  # Set the opacity of the ortho photo layer


        #add color to the SU ShapeFile layer
        self.layers_dict["SU_ShapeFile"].loadNamedStyle("Styles/SU_Pink.qml")

        #zoom the overview map item to the SU ShapeFile layer with a buffer and scale bar
        zoomToLayerWithBufferAndScalebar(self.maps["Page 1"]["Overview"], self.layers_dict[f"{self.su_info['trench']} overview boundary"], self.items_dict['Scalebar Overivew Page 1']["obj"], buffer_ratio=0)  # Zoom the overview map item to the SU ShapeFile layer with a buffer and scale bar
        zoomToLayerWithBufferAndScalebar(self.maps["Page 2"]["Overview"], self.layers_dict[f"{self.su_info['trench']} overview boundary"], self.items_dict['Scalebar Overview Page 2']["obj"], buffer_ratio=0)  # Zoom the overview map item to the SU ShapeFile layer with a buffer and scale bar


        active_layers = [self.layers_dict["architecture"], self.layers_dict["SU_ShapeFile"], self.layers_dict["trench-boundaries"]]  # List of active layers for the overview map item
        self.maps["Page 1"]["Overview"].setLayers(active_layers)  # Set the layers for the overview map item, page 1
        self.maps["Page 2"]["Overview"].setLayers(active_layers)  # Set the layers for the overview map item, page 1



        #lock the Overview map items
        lockItem(self.maps["Page 1"]["Overview"]) # Lock the overview map item, page 1
        lockItem(self.maps["Page 2"]["Overview"])  # Lock the overview map item, page 2


        #Ortho map
        print("Setting up Ortho map item...")

        self.layers_dict["ortho_photo"].setOpacity(1)  # Set the opacity of the ortho photo layer
        self.layers_dict["SU_ShapeFile"].loadNamedStyle("Styles/Ortho_SU_view_yellow_outline.qml")

        #zoom the ortho map item to the SU ShapeFile layer with a buffer and scale bar
        zoomToLayerWithBufferAndScalebar(self.maps["Page 1"]["Ortho"], self.layers_dict["SU_ShapeFile"], self.items_dict['Scalebar Ortho Page 1']["obj"])  # Zoom the overview map item to the SU ShapeFile layer with a buffer and scale bar
        zoomToLayerWithBufferAndScalebar(self.maps["Page 3"]["Ortho"], self.layers_dict["SU_ShapeFile"], self.items_dict['Scalebar Ortho Page 3']["obj"])  # Zoom the overview map item to the SU ShapeFile layer with a buffer and scale bar

        active_layers = [self.layers_dict["trench-boundaries"], self.layers_dict["architecture"], self.layers_dict["SU_ShapeFile"], self.layers_dict["ortho_photo"]]  # List of active layers for the overview map item
        self.maps["Page 1"]["Ortho"].setLayers(active_layers)  # Set the layers for the overview map item, page 1
        self.maps["Page 3"]["Ortho"].setLayers(active_layers)  # Set the layers for the overview map item, page 1

        #lock the ortho maps
        lockItem(self.maps["Page 1"]["Ortho"]) # Lock the overview map item, page 1
        lockItem(self.maps["Page 3"]["Ortho"])  # Lock the overview map item, page 2


        #DEM map
        print("Setting up DEM map item...")
        self.layers_dict["drone-flight"].setOpacity(1)
        self.layers_dict["dem_layer"].setOpacity(0.5)
        self.layers_dict["dem_lower_layer"].setOpacity(1)
        self.layers_dict["contour_layer"].setOpacity(1)  # Set the opacity of the contour layer
        self.layers_dict["SU_ShapeFile"].loadNamedStyle("Styles/SU_black_outline.qml")  # Load the style for the SU ShapeFile layer
        self.layers_dict["ortho_photo"].setOpacity(0)
        

        #zoom the DEM map item to the SU ShapeFile layer with a buffer and scale bar
        zoomToLayerWithBufferAndScalebar(self.maps["Page 1"]["DEM"], self.layers_dict["SU_ShapeFile"], self.items_dict['Scalebar DEM Page 1']["obj"])  # Zoom the overview map item to the SU ShapeFile layer with a buffer and scale bar
        zoomToLayerWithBufferAndScalebar(self.maps["Page 4"]["DEM"], self.layers_dict["SU_ShapeFile"], self.items_dict['Scalebar Overview Page 2']["obj"])  # Zoom the overview map item to the SU ShapeFile layer with a buffer and scale bar

        active_layers = [self.layers_dict["contour_layer"], self.layers_dict["trench-boundaries"], self.layers_dict["dem_layer"], self.layers_dict["dem_lower_layer"], self.layers_dict["architecture"], self.layers_dict["SU_ShapeFile"], self.layers_dict["drone-flight"]]  # List of active layers for the overview map item
        self.maps["Page 1"]["DEM"].setLayers(active_layers)  # Set the layers for the overview map item, page 1
        self.maps["Page 4"]["DEM"].setLayers(active_layers)  # Set the layers for the overview map item, page 1
        #lock DEM map items
        lockItem(self.maps["Page 1"]["DEM"])  # Lock the overview map item, page 2
        lockItem(self.maps["Page 4"]["DEM"])  # Lock the DEM map item, page 1



        # Set the elevation legend text
        self.items_dict["Higher Elevation Page 1"]["obj"].setText(str(self.elevation_stats['max_elevation']))  # Set the elevation legend text
        self.items_dict["High Elevation Page 4"]["obj"].setText(str(self.elevation_stats['max_elevation']))  # Set the elevation legend text
        self.items_dict["Lower Elevation Page 1"]["obj"].setText(str(self.elevation_stats['min_elevation']))  # Set the elevation legend text
        self.items_dict["Lower Elevation Page 4"]["obj"].setText(str(self.elevation_stats['min_elevation']))  # Set the elevation legend text


    
    
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
        



        #export the layout to PDF
        exporter = QgsLayoutExporter(self.layout)
        exporter.exportToPdf(pdf_path, QgsLayoutExporter.PdfExportSettings())




# SU_data = {
#     "SU": SU,
#     "TRENCH": TRENCH,
#     "JobID": JobID,
#     "description": "SU 17001 description specific",  # Add a description for the SU
#     "SU_ShapeFile_name": SU_ShapeFile_name,
#     "SU_ShapeFile": SU_ShapeFile,
#     "DEM_path": DEM_path,
# }




def generate_SU_Sheet(qgs, project, su, trench, job_id, year, description, pdf_path, qgs_project_template, photogrammetry_path, contour_interval=0.02):
    """Generates a SU sheet for the given SU, trench, and job ID.
    Args:   
        qgs (QgsApplication): The QGIS application instance.
        project (QgsProject): The QGIS project instance.
        su (str): The SU name.
        trench (str): The trench name.
        job_id (str): The job ID that opens this SU
        year (int): The year of the SU.
        description (str): Description of the SU.
        pdf_path (str): Path to save the generated PDF.
        qgs_project_template (str): Path to the QGIS project template file.
        photogrammetry_path (str): Path to the photogrammetry files."""

    # CONTOUR_INTERVAL = 0.02
    su_shapeFile_name = f"{su}_EPSG_32632.shp"
    su_shapefile_path = os.path.join(photogrammetry_path, "GIS_2025", "3D_SU_Shapefiles", su_shapeFile_name)  # Example shapefile name, change as needed
    DEM_path = get_DEM_path(job_id)
    # DEM_path = os.path.join("DEM",f"Pgram_Job_{job_id}_{su.replace('_', '')}_dem.tif")
    su_sheet_trench_template_path = f"SU_Layout_Templates/SU_Template_{trench.split(' ')[1]}.qpt"

    layers_dict = {}


    #adding it to the right trench and SU folder
    #create SU folder if it doesn't exist
    root = project.layerTreeRoot()

    #get the root directory of the project
    layers_dict["root"] = root  # Store the root in the dictionary


    print("Setting up QGIS file...")
    setupQGISFile(project, layers_dict)  # Set up the QGIS file by clearing existing layers and adding the drone flight layer


    #create the SU shp file if it doesn't exist
    if not os.path.exists(su_shapefile_path):
        print(f"Creating SU shapefile for {su}... (takes a while, 5-10 minutes)")


        #check if the Volumetrics su obj file exists
        su_volume_path = os.path.join(photogrammetry_path, "Volumetrics_2025", "SU Top OBJs", su+"_top.obj")

        if not os.path.exists(su_volume_path):
            raise FileNotFoundError(f"SU volume file {su_volume_path} not found. Please check the file path.")

        #CITATION: https://stackoverflow.com/questions/8391411/how-to-block-calls-to-print
        #hide logs
        with HiddenPrints():
            create_SU_shp_file({
                "obj_file": su_volume_path,
                "output_file_path": os.path.join(photogrammetry_path, "GIS_2025", "3D_SU_Shapefiles"),
                "su_number": int(su.split("_")[1]),
                "year": year
            })
        print(f"SU shapefile {su_shapefile_path} created successfully.")


    #add the ortho photo of the corresponing job id
    add_ortho_photo(job_id, project, layers_dict)


    #add a trench overview boundary layer
    print("Adding trench overview boundary layer...")
    trench_overview_layer = add_layer(f"{trench.replace(' ','_')}_Overview_Zoom_Rough_Boundary.shp", f"{trench} Overview Boundary", project)
    trench_overview_layer.setOpacity(0)  # make it transparent, since it only used for zooming in the overview map in the SU Sheet
    layers_dict[f"{trench} overview boundary"] = trench_overview_layer  # Store the trench overview boundary layer in the dictionary

    #add the trench boundaries and architecture 2025 layers
    print("Adding trench boundaries layer...")
    trench_boundaries_layer = add_layer("TARP 2025 Trench Boundaries 6-1-2025.shp", "Trench Boundaries", project)
    trench_boundaries_layer.loadNamedStyle("Styles/Trench_outline_style.qml")  # Load the style for the trench boundaries layer
    layers_dict["trench-boundaries"] = trench_boundaries_layer  # Store the trench boundaries layer in the dictionary


    print("Adding architecture 2025 layer...")
    architecture_layer = add_layer("Architecture_2025.shp", "Architecture 2025", project)
    architecture_layer.loadNamedStyle("Styles/TARP_Architecture_Colored_Style_2025.qml")  # Load the style for the architecture layer
    layers_dict["architecture"] = architecture_layer  # Store the architecture layer in the dictionary 






    # Check if the SU Shape layer already exists in the SU folder
    # if project.mapLayersByName(SU_ShapeFile_name) is None:
    #     #add the layer to the SU folder
    print("Adding SU shapefile layer...")
    su_shape_layer = add_layer(su_shapefile_path,su_shapeFile_name, project)
    layers_dict["SU_ShapeFile"] = su_shape_layer  # Store the layer in the dictionary



    # # print("clipping DEM to the mask layer...")
    # # Print the trench folder name
    # #clip DEM to the mask layer
    clipRaster(
        input_raster=DEM_path,
        mask_layer=su_shapefile_path,
        output_path=su+"_DEM.tif"
    )

    #get contours from the clipped DEM
    contour_file = get_contours(su+"_DEM.tif", su, interval=contour_interval)
    print("Contour file generated:", contour_file)



    dem_layer, dem_lower_layer, elevation_stats = add_DEM(su+"_DEM.tif", project)
    layers_dict["dem_layer"] =  dem_layer # Store the layer in the dictionary
    layers_dict["dem_lower_layer"] =  dem_lower_layer # Store the layer in the dictionary

    #add the contour layer to the SU folder
    contour_layer = add_contour(contour_file, project)
    layers_dict["contour_layer"] =  contour_layer # Store the layer in the dictionary

    #CITATION: https://stackoverflow.com/questions/8391411/how-to-block-calls-to-print
    #hide logs
    # with HiddenPrints():
        #create an SU Sheet
    su_sheet = SUSheet(su_sheet_trench_template_path, su, trench, description, pdf_path, elevation_stats, layers_dict)

    #manipulate the layout items
    print("Manipulating layout items...")


    #generate the SU Sheet PDF
    su_sheet.generatePDF(pdf_path)  # Generate the PDF using the template






    #UNCOMMENT TO SAVE THE PROJECT
    print("saving project...")
    project.write()  # Save the project after adding the layer










# # # Load another project

# print(os.listdir(project.absoluteFilePath()))



 





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


def load_project(qgs_project_template_path):
    """Loads a QGIS project from the specified path."""
    project = QgsProject.instance()

    if not os.path.exists(qgs_project_template_path):
        raise FileNotFoundError(f"Project file {qgs_project_template_path} not found. Please check the file path.")

    print("Loading project...")
    project.read(qgs_project_template_path)  # Load the project file
    return project
    

def close_QGS(qgs):
    """Exits the QGIS application."""
    print("Exiting QGIS Application...")
    qgs.exitQgis()

# qgs = start_QGS()  # Start the QGIS application

# # Generate the SU Sheet
# try:
#     # generate_SU_Sheet(qgs, SU, TRENCH, JobID, YEAR, DESCRIPTION, TEMPLATE_PDF_PATH, QGS_FILE_NAME, PATH)
#     generate_SU_Sheet(qgs, "SU_17001", "Trench "+"SU_17001"[-5:-3]+"000", "707", "2025", "SU 17001 description specific", "new_layout.pdf", QGS_FILE_NAME, PATH)
#     print("SU Sheet generated successfully.")
# except Exception as e:
#     print(f"Error generating SU Sheet: {e}")




# # Exit QGIS Application
# print("Exiting QGIS Application...")
# qgs.exitQgis()