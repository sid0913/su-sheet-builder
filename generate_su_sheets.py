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

    def contains_no_numbers(input_string):
        """
        Checks if a string contains no numbers.

        Args:
            input_string: The string to check.

        Returns:
            True if the string contains no numbers, False otherwise.
        """
        for char in input_string:
            if char.isdigit():
                return False  # Found a digit, so it contains numbers
        return True  # No digits found, so it contains no numbers

    def import_filemaker_su_data(file_path):
        """
        Import SU sheet data from an Excel file.
        """
        try:
            df = pd.read_excel(file_path)
            df = modify_filemaker_su_data(df)  # Modify the DataFrame as needed
            print(df.head())  # Display the first few rows of the DataFrame

            print("Data imported and modified successfully.")
            return df
        except Exception as e:
            print(f"Error importing SU sheet data: {e}")
            return pd.DataFrame()
        

    def get_jobs_from_pgram_csv(pgram_csv_path):
        """
        Get photogrammetry information from a CSV file.
        """
        try:
            pgram_df = pd.read_csv(pgram_csv_path)
            return  modify_pgram_csv(pgram_df)  # Modify the DataFrame as needed
        except Exception as e:
            print(f"Error importing photogrammetry information: {e}")
            return None
    
    def convert_ranges_to_list(ranges):
        """
        Convert a string of ranges like '18001-18005,18007' into a list of integers.
        """
        result = []
        for part in ranges.strip().split(','):
            if '-' in part:
                start, end = map(int, part.split('-'))
                result.extend(range(start, end + 1))
            else:
                result.append(int(part))
        return result
    
    def modify_pgram_csv(df, min_trench = 17000, max_trench = 20000):
        """
        Modify the DataFrame as needed and add the jobs to missing spots in the SU sheet data.
        This function processes the DataFrame to extract job IDs and SUs from the 'Pgram Number' and 'SUs Open' columns.
        It filters out rows with invalid or missing data, converts ranges in 'SUs Open' to lists, and creates a new DataFrame with the results.
        Args:           
            df (pd.DataFrame): The DataFrame containing photogrammetry job data.
            su_sheet_data (pd.DataFrame): The DataFrame containing SU sheet data.
            min_trench (int): Minimum trench number to consider.
            max_trench (int): Maximum trench number to consider.
        Returns:
            pd.DataFrame: A new DataFrame containing the processed job IDs and SUs.
        """

        new_df = pd.DataFrame(columns=["SU", "job_id"])  # Create a new DataFrame to store the results

        df = df[~df['Pgram Number'].isna() & (df['Pgram Number'] != '')]  # Remove rows where 'Pgram Number' is NaN or empty
        df = df[~df['Pgram Number'].isna() & (df['SUs Open'] != '') ]  # Remove rows where 'Pgram Number' is NaN or empty
        

        df["SUs Open"] = df['SUs Open'].astype(str)  # Ensure 'SUs Open' column is of string type


        df = df[df.apply(lambda x: not contains_no_numbers(x['SUs Open']), axis=1)]  # Filter rows where 'SUs Open' contains no numbers

        # Example modification: add a new column
        df['Pgram Number'] = df['Pgram Number'].astype(int).astype(str)  # Ensure 'Pgram Number' column is of string type
        for index, row in df.iterrows():
            job_id = row['Pgram Number']
            if job_id  == '717':  # Skip job ID 717
                continue
            
            if pd.isna(job_id) or job_id == '' :
                raise(f"Job ID is missing in row {index}. Please check the CSV file.")
            SUs = convert_ranges_to_list(row['SUs Open'])
            for su in SUs:
                # if su <= min_trench or su > max_trench:
                #     continue
                # print(f"Processing SU: {su} with Job ID: {job_id}")
                new_df = pd.concat([new_df , pd.DataFrame({"SU": [f"{su}"], "job_id": [job_id]})])  # Append the row to the new DataFrame
                # su_sheet_df.loc[su_sheet_df['SU'] == f"SU_{su}", 'job_id'] = job_id  # Update the job_id in the su_sheet_df DataFrame
                # su_sheet_df.loc[su_sheet_df['job_id'] == job_id, 'SU'] = f"SU_{su}"  # Update the description in the su_sheet_df DataFrame
        # print(f"Total number of jobs found: {len(new_df)}")


        new_df = new_df[new_df.apply(lambda x: min_trench <= int(x['SU']) < max_trench, axis=1)]
        # new_df.to_excel(os.path.join(PATH, "GIS_2025", "pgram_jobs_new.xlsx"), index=False)  # Save the modified DataFrame to an Excel file
        return new_df

        
    def shp_file_exists(su, photogrammetry_path):
        su_shapeFile_name = f"{su}_EPSG_32632.shp"
        su_shapefile_path = os.path.join(photogrammetry_path, "GIS_2025", "3D_SU_Shapefiles", su_shapeFile_name)

        return os.path.exists(su_shapefile_path)

    def modify_filemaker_su_data(df):
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
    
    df = import_filemaker_su_data("SUs for spatial sheets.xlsx")
    df.to_excel(os.path.join(PATH, "GIS_2025", "df.xlsx"), index=False)  # Save the modified DataFrame to an Excel file
    pgram_data = get_jobs_from_pgram_csv(os.path.join(PATH, "GIS_2025", "TARP 2025 Photogrammetry Job Tracking - Pgram Jobs.csv"))  # Example path to the CSV file

    final_df = pd.DataFrame(columns=["SU", "Short Description", "Long Description", "job_id"])  # Create a new DataFrame to store the results

    for index, row in pgram_data.iterrows():
        su = f"SU_{row['SU']}"
        job_id = row['job_id']
        
        description = ""
        long_description = ""

        # Check if the SU exists in the pgram_data DataFrame
        if su in df['SU'].values:
            # print(f"FOUND SU: {su} with Job ID: {job_id}")
            description = df.loc[df['SU'] == su, 'Short Description'].values[0] if not df.loc[df['SU'] == su, 'Short Description'].empty else ""
            long_description = df.loc[df['SU'] == su, 'Long Description'].values[0] if not df.loc[df['SU'] == su, 'Long Description'].empty else ""
        else:
            # pass
            print(f"SU {su} not found in the DataFrame, skipping...", len(su))
            # print(f"Available SUs: {[ x for x in df['SU'].unique() if '18' in x]}")  # Print available SUs for debugging
            
        final_df = pd.concat([final_df, pd.DataFrame({"SU": [su], "Short Description": [description], "Long Description": [long_description], "job_id": [job_id]})])  # Append the row to the new DataFrame
    
    # final_df.to_excel(os.path.join(PATH, "GIS_2025", "ready_sus.xlsx"), index=False)  # Save the modified DataFrame to an Excel file
    # # df.to_excel(os.path.join( "final.xlsx"), index=False)
    # print("succcessfully imported and modified the data")

    df = final_df

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
    print(f"Total number of SUs in the DataFrame: {len(df['SU'].unique())}")
    print(f"Total number of SUs in the DataFrame: {len(df.drop_duplicates()['SU'])}")


    # ready_sus_df.to_excel(os.path.join(PATH, "GIS_2025", "ready_sus.xlsx"), index=False)  # Save the modified DataFrame to an Excel file
    # for index, [su, description, long_description, job_id] in ready_sus_df.iterrows():
    #     print(f"SU: {su}, Description: {description}, Long Description: {long_description}, Job ID: {job_id}")

    # qgs = start_QGS()  # Start the QGIS application
    # project = load_project(QGS_FILE_NAME)



    # start = time.time()
    # #this does work for skipping errors and keeping the script running, 
    # # for su,job_id in [("SU_17001", "707"), (SU, JobID), ("SU_18001", "708")]: 
    # for index, [su, description, long_description, job_id] in ready_sus_df.iterrows():
    # # for su,job_id in [("SU_17001", "707"), ("SU_18003", "711")]: #these work
    #     try:
    #         trench = "Trench "+su[-5:-3]+"000"
    #         # description = f"This is {su} description specific"

    #         su_sheet_pdf_path = os.path.join("SU_Sheets","SU_Sheet_PDFs", trench, f"{su}.pdf")
    #         print(f"Generating SU Sheet for {su} in {trench} with Job ID {job_id}...")

    #         if os.path.exists(su_sheet_pdf_path):
    #             print(f"SU Sheet {su_sheet_pdf_path} already exists, skipping...")
    #             continue

    #         if not shp_file_exists(su, PATH):
    #             print(f"Shapefile for {su} does not exist, skipping...")
    #             continue
    #         generate_SU_Sheet(qgs, project, su, trench, job_id, YEAR, description, su_sheet_pdf_path, QGS_FILE_NAME, PATH)
    #         # generate_SU_Sheet(qgs, "SU_17001", "Trench "+"SU_17001"[-5:-3]+"000", "707", "2025", "SU 17001 description specific", "new_layout.pdf", QGS_FILE_NAME, PATH)
    
    #     except Exception as e:
    #         print(f"Error generating SU Sheet: {e}")
    #         #open error text file and write the error message
    #         with open(os.path.join(PATH, "GIS_2025", "error_log.txt"), "a") as error_file:
    #             error_file.write(f"{datetime.now(pytz.timezone('Europe/Rome')).strftime("%Y-%m-%d %H:%M:%S")} -- Error generating SU Sheet for {su}: {e}\n")
    #         continue
    # end = time.time()
    # mins_elapsed = (end - start) / 60
    # print(f"Time elapsed: {mins_elapsed:.2f} minutes")
    # close_QGS(qgs)  # Close the QGIS application