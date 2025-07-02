"""
Model exported as python.
Name : Convert 3D OBJ to 3D SHP Polygon 2024
Group : TARP
With QGIS : 33601
"""
#This version works with relative paths on Windows, MacOSX or Linux systems
#A folder is created in the user directory with another python script and to store temporary shapefiles
#Blender must also be installed on the system
#The Blender-GIS Addon must also be installed
#The Blender.exe file will be found in the Program Files (Windows) or Applications (MacOS) directory
#If installed in another location, script might fail
#Warning - MacOSX and Linux functionality is untested!

# import sys
# sys.path = ['', 'C:\\PROGRA~1\\QGIS34~1.8\\apps\\qgis-ltr\\python', 'C:\\Program Files\\QGIS 3.40.8\\bin', 'C:\\Program Files\\QGIS 3.40.8\\bin\\python312.zip', 'C:\\PROGRA~1\\QGIS34~1.8\\apps\\Python312\\DLLs', 'C:\\PROGRA~1\\QGIS34~1.8\\apps\\Python312\\Lib', 'C:\\PROGRA~1\\QGIS34~1.8\\apps\\Python312', 'C:\\PROGRA~1\\QGIS34~1.8\\apps\\Python312\\Lib\\site-packages', 'C:\\PROGRA~1\\QGIS34~1.8\\apps\\Python312\\Lib\\site-packages\\win32', 'C:\\PROGRA~1\\QGIS34~1.8\\apps\\Python312\\Lib\\site-packages\\win32\\lib', 'C:\\PROGRA~1\\QGIS34~1.8\\apps\\Python312\\Lib\\site-packages\\Pythonwin']
# sys.path.append("C:\\Program Files\\QGIS 3.40.8\\apps\\qgis-ltr\\python\\plugins")


from qgis.core import QgsProject
from qgis.core import QgsProcessing
from qgis.core import QgsProcessingAlgorithm
from qgis.core import QgsProcessingParameterNumber
from qgis.core import QgsProcessingParameterFile
from qgis.core import QgsCoordinateReferenceSystem
import processing
import subprocess
import platform
from pathlib import Path
import math



def create_SU_shp_file(parameters):
    """ Process the algorithm with the given parameters and context.
    :param parameters: Dictionary of parameters for the algorithm.
    """
    # Use a multi-step feedback, so that individual child algorithm progress reports are adjusted for the
    # overall progress through the model
    results = {}
    outputs = {}
    root = Path.home().parent.parent

    #Create output path objects for interoperability - create filenames and paths
    new_output_path = Path(parameters ['output_file_path'])
    print("new output path: ", new_output_path)
    local_filename = 'SU_' + str(parameters['su_number']) + '_LC.shp'
    global_filename = 'SU_' + str(parameters['su_number']) + '_EPSG_32632.shp'
    local_path = Path.joinpath(new_output_path, local_filename)
    print("local path: ", local_path)
    global_path = Path.joinpath(new_output_path, global_filename)
    print("global path: ", global_path)

    #Locates the path of Blender application executable
    if platform.system() == 'Windows':
        blender_path = sorted(Path.joinpath(root, 'Program Files', 'Blender Foundation').glob('**/blender.exe'))
    elif platform.system() == 'Linux':
        blender_path = sorted(Path.joinpath(root).glob('**/blender'))
    else:
        blender_path = sorted(Path.joinpath(root, 'Applications').glob('**/blender'))
        
    #Location where the program folder will be created - user home directory subfolder called "SU_tool"
    tool_dir = Path.home() / 'SU_tool'
    tool_dir.mkdir(parents=True, exist_ok=True)
    print("tool dir: ", tool_dir)
    print(Path.joinpath(tool_dir, "Run BlenderGIS headless.py"))

    #Python script that gets saved to program folder
    script = "import bpy\nimport sys\nfrom pathlib import Path\nargv = sys.argv[7]\nprint(argv)\ntool_dir = Path.joinpath(Path.home(), 'SU_tool')\noutput = Path.joinpath(tool_dir,'tmp_SU.shp')\noutput1 = str(output)\nbpy.ops.wm.obj_import(filepath=argv, forward_axis='Y', up_axis='Z')\nbpy.ops.exportgis.shapefile(filepath=output1, objectsSource='SELECTED', exportType='POLYGONZ', mode='OBJ2FEAT')"
    filename = Path.joinpath(tool_dir, "Run BlenderGIS headless.py")
    if not filename.exists():
        filename.write_text(script)

    #Run Blender in Headless mode and export temporary shapefile
    subprocess.call([blender_path[0], '-b', '--addons', 'BlenderGIS-master', '--python', str(filename), '--', parameters['obj_file']], shell = True)

    # Fix geometries - Takes temporary shapefile exported by Blender
    temp_shp = Path.joinpath(tool_dir,"tmp_SU.shp")
    print("temp shp: ", temp_shp)
    print("Handing the processing to QGIS for some final shape file processing... (5 minutes)")
    alg_params = {
        'INPUT': str(temp_shp),
        'METHOD': 1,  # Structure
        'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
    }
    outputs['FixGeometries'] = processing.run('native:fixgeometries', alg_params)



    # Dissolve
    alg_params = {
        'FIELD': [''],
        'INPUT': outputs['FixGeometries']['OUTPUT'],
        'SEPARATE_DISJOINT': False,
        'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
    }
    outputs['Dissolve'] = processing.run('native:dissolve', alg_params)



    # Delete holes
    alg_params = {
        'INPUT': outputs['Dissolve']['OUTPUT'],
        'MIN_AREA': 0,
        'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
    }
    outputs['DeleteHoles'] = processing.run('native:deleteholes', alg_params)


        
    # Fix geometries again
    alg_params = {
        'INPUT': outputs['DeleteHoles']['OUTPUT'],
        'METHOD': 1,  # Structure
        'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
    }
    outputs['FixGeometries'] = processing.run('native:fixgeometries', alg_params)



    # Save local coordinate vector file
    alg_params = {
        'ACTION_ON_EXISTING_FILE': 0,  # Create or overwrite file
        'DATASOURCE_OPTIONS': '',
        'INPUT': outputs['FixGeometries']['OUTPUT'],
        'LAYER_NAME': '',
        'LAYER_OPTIONS': '',
        'OUTPUT': str(local_path)
    }
    outputs['SaveVectorFeaturesToFile'] = processing.run('native:savefeatures', alg_params)



    # Translate to Projected Coordinates - These can be changed if necessary
    alg_params = {
        'DELTA_M': 0,
        'DELTA_X': 452000,
        'DELTA_Y': 4413000,
        'DELTA_Z': 0,
        'INPUT': outputs['FixGeometries']['OUTPUT'],
        'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
    }
    outputs['Translate'] = processing.run('native:translategeometry', alg_params)



    # Assign projection - Necessary after translating coordinates
    alg_params = {
        'CRS': QgsCoordinateReferenceSystem('EPSG:32632'),
        'INPUT': outputs['Translate']['OUTPUT'],
        'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
    }
    outputs['AssignProjection'] = processing.run('native:assignprojection', alg_params)



    # Field calculator Year - Takes value input by user in "Year" and assigns to new field
    alg_params = {
        'FIELD_LENGTH': 0,
        'FIELD_NAME': 'Year',
        'FIELD_PRECISION': 0,
        'FIELD_TYPE': 1,  # Integer (32 bit)
        'FORMULA': parameters['year'],
        'INPUT': outputs['AssignProjection']['OUTPUT'],
        'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
    }
    outputs['FieldCalculatorYear'] = processing.run('native:fieldcalculator', alg_params)



    # Field calculator Trench - Create trench number and assigns to field "Trench"
    alg_params = {
        'FIELD_LENGTH': 0,
        'FIELD_NAME': 'Trench',
        'FIELD_PRECISION': 0,
        'FIELD_TYPE': 1,  # Integer (32 bit)
        'FORMULA': (math.floor(parameters['su_number']/1000))*1000,
        'INPUT': outputs['FieldCalculatorYear']['OUTPUT'],
        'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
    }
    outputs['FieldCalculatorTrench'] = processing.run('native:fieldcalculator', alg_params)



    # Field calculator SU - Takes SU number input by user and assigns to new field "SU"
    alg_params = {
        'FIELD_LENGTH': 0,
        'FIELD_NAME': 'SU',
        'FIELD_PRECISION': 0,
        'FIELD_TYPE': 1,  # Integer (32 bit)
        'FORMULA': parameters['su_number'],
        'INPUT': outputs['FieldCalculatorTrench']['OUTPUT'],
        'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
    }
    outputs['FieldCalculatorSu'] = processing.run('native:fieldcalculator', alg_params)



    # Save projected vector file
    alg_params = {
        'ACTION_ON_EXISTING_FILE': 0,  # Create or overwrite file
        'DATASOURCE_OPTIONS': '',
        'INPUT': outputs['FieldCalculatorSu']['OUTPUT'],
        'LAYER_NAME': '',
        'LAYER_OPTIONS': '',
        'OUTPUT': str(global_path)
    }
    outputs['SaveVectorFeaturesToFile'] = processing.run('native:savefeatures', alg_params)


    # Load layer into project
    alg_params = {
        'INPUT': outputs['SaveVectorFeaturesToFile']['OUTPUT'],
        'NAME': global_filename
    }
    outputs['LoadLayerIntoProject'] = processing.run('native:loadlayer', alg_params)
    return results




