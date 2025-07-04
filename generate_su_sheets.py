from qgs_su_sheets_utils import start_QGS, generate_SU_Sheet, close_QGS, load_project
import os 
import pytz
from datetime import datetime
import time

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
    

    
    qgs = start_QGS()  # Start the QGIS application
    project = load_project(QGS_FILE_NAME)



    start = time.time()
    #this does work for skipping errors and keeping the script running, 
    for su,job_id in [("SU_17001", "707"), (SU, JobID), ("SU_18001", "708")]: #the last two don't work for some reason
    # for su,job_id in [("SU_17001", "707"), ("SU_18003", "711")]: #these work
        try:
            trench = "Trench "+su[-5:-3]+"000"
            description = f"This is {su} description specific"

            su_sheet_pdf_path = os.path.join(PATH, "AutomateRockMask", "SU_Sheets", "SU_Sheet_PDFs",f"{su}.pdf)")
            print(f"Generating SU Sheet for {su} in {trench} with Job ID {job_id}...")

            if os.path.exists(os.path.join(PATH, "AutomateRockMask", su_sheet_pdf_path)):
                print(f"SU Sheet {su_sheet_pdf_path} already exists, skipping...")
                continue


            generate_SU_Sheet(qgs, project, su, trench, job_id, YEAR, description, os.path.join("SU_Sheets","SU_Sheet_PDFs", f"{su}.pdf"), QGS_FILE_NAME, PATH)
            # generate_SU_Sheet(qgs, "SU_17001", "Trench "+"SU_17001"[-5:-3]+"000", "707", "2025", "SU 17001 description specific", "new_layout.pdf", QGS_FILE_NAME, PATH)
    
        except Exception as e:
            print(f"Error generating SU Sheet: {e}")
            #open error text file and write the error message
            with open(os.path.join(PATH, "AutomateRockMask", "error_log.txt"), "a") as error_file:
                error_file.write(f"{datetime.now(pytz.timezone('Europe/Rome')).strftime("%Y-%m-%d %H:%M:%S")} -- Error generating SU Sheet for {su}: {e}\n")
            continue
    end = time.time()
    mins_elapsed = (end - start) / 60
    print(f"Time elapsed: {mins_elapsed:.2f} minutes")
    close_QGS(qgs)  # Close the QGIS application