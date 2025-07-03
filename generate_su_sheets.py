from qgs_su_sheets_utils import start_QGS, generate_SU_Sheet, close_QGS

if __name__ == "__main__":
    QGS_FILE_NAME="TARP_SU_Sheets_2025_test_updating_v2.qgs"
    PATH = "C:\\Users\\Photogrammetry"


    #placeholder values
    SU = "SU_18003"  # Example SU name, change as needed
    TRENCH = "Trench "+SU[-5:-3]+"000"  # Extract trench number from SU name
    JobID = "711"
    TEMPLATE_PDF_PATH = "new_layout.pdf"  # Path to the template PDF file, change as needed
    YEAR = "2025"  # Example year, change as needed
    DESCRIPTION = f"This is {SU} description "  # Add a description for the SU
    
    
    qgs = start_QGS()  # Start the QGIS application

    try:
        generate_SU_Sheet(qgs, SU, TRENCH, JobID, YEAR, DESCRIPTION, TEMPLATE_PDF_PATH, QGS_FILE_NAME, PATH)
        # generate_SU_Sheet(qgs, "SU_17001", "Trench "+"SU_17001"[-5:-3]+"000", "707", "2025", "SU 17001 description specific", "new_layout.pdf", QGS_FILE_NAME, PATH)
    
    except Exception as e:
        print(f"Error generating SU Sheet: {e}")

    finally:
        close_QGS(qgs)  # Close the QGIS application