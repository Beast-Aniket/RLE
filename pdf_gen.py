from pathlib import Path
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from pdf_config import PDF_SETTINGS

OUT_DIR = Path("letters")
OUT_DIR.mkdir(exist_ok=True)


def generate_letter(request_row: dict) -> str:
    file_path = OUT_DIR / f"request_{request_row['request_id']}.pdf"
    c = canvas.Canvas(str(file_path), pagesize=A4)
    y = 800
    c.setFont("Helvetica-Bold", 14)
    c.drawString(50, y, PDF_SETTINGS["title"])
    y -= 30
    c.setFont("Helvetica", 11)
    for line in [
        f"Session: {request_row['session_name']}",
        f"Exam: {request_row['exam_name']} ({request_row['program_code']})",
        f"Student: {request_row['student_name']} | PRN: {request_row['prn']} | Seat: {request_row['seat_no']}",
        f"Result Status: {request_row['result_status']}",
        f"CGPI: {request_row['cgpi']}",
        f"Remark: {request_row['remark']}",
        f"Admin Comment: {request_row.get('admin_comment','')}",
    ]:
        c.drawString(50, y, line)
        y -= 20
    c.drawString(50, 120, PDF_SETTINGS["issuer"])
    c.drawString(50, 100, PDF_SETTINGS["signature_label"])
    c.drawString(50, 60, PDF_SETTINGS["footer"])
    c.save()
    return str(file_path)
