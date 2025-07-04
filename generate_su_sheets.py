from qgs_su_sheets_utils import start_QGS, generate_SU_Sheet, close_QGS, load_project
import os 
import pytz
from datetime import datetime
import time
import pandas as pd
import numpy as np

if __name__ == "__main__":
    QGS_FILE_NAME="TARP_SU_Sheets_2025.qgs"
    PATH = "C:\\Users\\Photogrammetry"


    #placeholder values
    SU = "SU_19001"  # Example SU name, change as needed
    TRENCH = "Trench "+SU[-5:-3]+"000"  # Extract trench number from SU name
    JobID = "709"
    TEMPLATE_PDF_PATH = "new_layout.pdf"  # Path to the template PDF file, change as needed
    YEAR = "2025"  # Example year, change as needed
    DESCRIPTION = f"This is {SU} description "  # Add a description for the SU

    def import_su_sheet_data(file_path):
        """
        Import SU sheet data from an Excel file.
        """
        try:
            df = pd.read_excel(file_path)
            df = modify_df(df)  # Modify the DataFrame as needed
            print(df.head())  # Display the first few rows of the DataFrame

            print("Data imported and modified successfully.")
            return df
        except Exception as e:
            print(f"Error importing SU sheet data: {e}")
            return pd.DataFrame()
        

    def shp_file_exists(su, photogrammetry_path):
        su_shapeFile_name = f"{su}_EPSG_32632.shp"
        su_shapefile_path = os.path.join(photogrammetry_path, "GIS_2025", "3D_SU_Shapefiles", su_shapeFile_name)

        return os.path.exists(su_shapefile_path)

    def modify_df(df):
        """
        Modify the DataFrame as needed.
        This is a placeholder function; implement your logic here.
        """
        # Example modification: add a new column

        #remove the rows where 'SU' column is NaN or empty 
        df = df[~df['SU'].isna() & (df['SU'] != '')]
        df = df[df['SU'] >= 17000 ]  # Filter rows where 'SU' starts with 'SU_'
        df = df[df['SU'] < 20000 ]  # Filter rows where 'SU' starts with 'SU_'
        df['SU'] = df['SU'].astype(int).astype(str)  # Ensure 'SU' column is of string type
        df['SU'] = "SU_"+df['SU']  # Remove leading and trailing
        df['job_id']  = df['Photogrammetry Jobs_Subject _ Link_open 2::Photogrammetry Job ID']
        df.drop(columns=['Photogrammetry Jobs_Subject _ Link_open 2::Photogrammetry Job ID'], inplace=True)  # Drop the original column
        # print("this is the total is",np.sum(np.array(df['job_id'].isna())))  # Get the length of the 'SU' column
        df = df[~df['job_id'].isna() & (df['job_id'] != '')]
        df['job_id'] = [s.strip().split(' ')[-1] for s in df['job_id']]   # Ensure 'job_id' column is of string type



        return df
    
    df = import_su_sheet_data("SUs for spatial sheets.xlsx")
    # df.to_excel(os.path.join( "final.xlsx"), index=False)
    print("succcessfully imported and modified the data")

    ready_sus_df = pd.DataFrame(columns=df.columns)  # Create a new DataFrame to store the results
    #check how many su tops exist for each su in the DataFrame
    count = 0
    df_sus = df['SU'].unique()  # Get unique SU values from the DataFrame
    for index, su in enumerate(df_sus):
        top_file_path = os.path.join(PATH, "Volumetrics_2025", "SU Top OBJs", f"{su}_top.obj")
        if os.path.exists(top_file_path):
            count += 1
            ready_sus_df = pd.concat([ready_sus_df, df[df['SU'] == su]])  # Append the row to the new DataFrame

    print(f"Total number of SU tops found: {count}")
    print(f"Total number of SUs ready for processing: {len(ready_sus_df)}")

    # for index, [su, description, long_description, job_id] in ready_sus_df.iterrows():
    #     print(f"SU: {su}, Description: {description}, Long Description: {long_description}, Job ID: {job_id}")

    qgs = start_QGS()  # Start the QGIS application
    project = load_project(QGS_FILE_NAME)



    start = time.time()
    #this does work for skipping errors and keeping the script running, 
    # for su,job_id in [("SU_17001", "707"), (SU, JobID), ("SU_18001", "708")]: 
    for index, [su, description, long_description, job_id] in ready_sus_df.iterrows():
    # for su,job_id in [("SU_17001", "707"), ("SU_18003", "711")]: #these work
        try:
            trench = "Trench "+su[-5:-3]+"000"
            # description = f"This is {su} description specific"

            su_sheet_pdf_path = os.path.join(PATH, "GIS_2025", "SU_Sheets", "SU_Sheet_PDFs",f"{su}.pdf)")
            print(f"Generating SU Sheet for {su} in {trench} with Job ID {job_id}...")

            if os.path.exists(os.path.join(PATH, "GIS_2025", su_sheet_pdf_path)):
                print(f"SU Sheet {su_sheet_pdf_path} already exists, skipping...")
                with open(os.path.join(PATH, "GIS_2025", "error_log.txt"), "a") as error_file:
                    error_file.write(f"{datetime.now(pytz.timezone('Europe/Rome')).strftime("%Y-%m-%d %H:%M:%S")} -- Error generating SU Sheet for {su}: {e}\n")
                continue

            if not shp_file_exists(su, PATH):
                print(f"Shapefile for {su} does not exist, skipping...")
                continue
            generate_SU_Sheet(qgs, project, su, trench, job_id, YEAR, description, os.path.join("SU_Sheets","SU_Sheet_PDFs", trench, f"{su}.pdf"), QGS_FILE_NAME, PATH)
            # generate_SU_Sheet(qgs, "SU_17001", "Trench "+"SU_17001"[-5:-3]+"000", "707", "2025", "SU 17001 description specific", "new_layout.pdf", QGS_FILE_NAME, PATH)
    
        except Exception as e:
            print(f"Error generating SU Sheet: {e}")
            #open error text file and write the error message
            with open(os.path.join(PATH, "GIS_2025", "error_log.txt"), "a") as error_file:
                error_file.write(f"{datetime.now(pytz.timezone('Europe/Rome')).strftime("%Y-%m-%d %H:%M:%S")} -- Error generating SU Sheet for {su}: {e}\n")
            continue
    end = time.time()
    mins_elapsed = (end - start) / 60
    print(f"Time elapsed: {mins_elapsed:.2f} minutes")
    close_QGS(qgs)  # Close the QGIS application