from qgs_su_sheets_utils import start_QGS, generate_SU_Sheet, close_QGS
import os
import json
import pytz
from datetime import datetime


def _report_progress(processed, total, label=""):
    """Write per-SU progress for the dashboard's determinate bar (atomic, best-effort)."""
    try:
        with open("progress.json.tmp", "w") as f:
            f.write(json.dumps({"processed": processed, "total": total, "label": label}))
        os.replace("progress.json.tmp", "progress.json")
    except OSError:
        pass


if __name__ == "__main__":
    QGS_FILE_NAME="TARP_SU_Sheets_2026.qgs"
    PATH = "C:\\Users\\Photogrammetry"


    # Batch input written by the dashboard's Create-SU-Sheet button (one run for all SUs).
    INPUT_FILE = "su_sheets_input.json"
    if not os.path.exists(INPUT_FILE):
        raise RuntimeError(
            f"No '{INPUT_FILE}' found in {os.getcwd()}. This script is driven by the dashboard's "
            f"Create-SU-Sheet button, which writes that file before launching. "
            f"Run it from the dashboard, not directly."
        )
    with open(INPUT_FILE, "r") as f:
        _su_input = json.load(f)
    YEAR = str(_su_input.get("year", ""))
    work = [(item["su"], item["job_id"]) for item in _su_input.get("items", [])]
    if not work:
        raise RuntimeError(f"'{INPUT_FILE}' contains no SU items to process.")


    
    qgs = start_QGS()  # Start the QGIS application

    total = len(work)
    _report_progress(0, total)

    for done, (su, job_id) in enumerate(work, start=1):
        _report_progress(done, total, su)
        try:
            trench = "Trench "+su[-5:-3]+"000"
            description = f"This is {su} description specific"

            # SU sheets are written into the per-year Volumetrics folder.
            su_sheet_dir = os.path.join(PATH, f"Volumetrics_{YEAR}")
            os.makedirs(su_sheet_dir, exist_ok=True)
            su_sheet_pdf_path = os.path.join(su_sheet_dir, f"{su}.pdf")
            print(f"Generating SU Sheet for {su} in {trench} with Job ID {job_id}...")

            if os.path.exists(su_sheet_pdf_path):
                print(f"SU Sheet {su_sheet_pdf_path} already exists, skipping...")
                continue


            generate_SU_Sheet(qgs, su, trench, job_id, YEAR, description, su_sheet_pdf_path, QGS_FILE_NAME, PATH)
            # generate_SU_Sheet(qgs, "SU_17001", "Trench "+"SU_17001"[-5:-3]+"000", "707", "2025", "SU 17001 description specific", "new_layout.pdf", QGS_FILE_NAME, PATH)
    
        except Exception as e:
            print(f"Error generating SU Sheet: {e}")
            #open error text file and write the error message
            with open(os.path.join(PATH, "AutomateRockMask", "error_log.txt"), "a") as error_file:
                error_file.write(f"{datetime.now(pytz.timezone('Europe/Rome')).strftime("%Y-%m-%d %H:%M:%S")} -- Error generating SU Sheet for {su}: {e}\n")
            continue

    close_QGS(qgs)  # Close the QGIS application