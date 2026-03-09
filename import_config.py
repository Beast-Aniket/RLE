"""Configurable source-column alias mapping for student imports."""

COLUMN_ALIASES = {
    "name": ["name", "student_name", "student name", "fullname"],
    "prn": ["prn", "prn_no", "prn number"],
    "seat_no": ["seat_no", "seat number", "seatno", "seat"],
    "sex": ["sex", "gender"],
    "sem1_gpi": ["sem1", "sem1_gpi", "sem 1 gpi"],
    "sem2_gpi": ["sem2", "sem2_gpi", "sem 2 gpi"],
    "sem3_gpi": ["sem3", "sem3_gpi", "sem 3 gpi"],
    "sem4_gpi": ["sem4", "sem4_gpi", "sem 4 gpi"],
    "sem5_gpi": ["sem5", "sem5_gpi", "sem 5 gpi"],
    "sem6_gpi": ["sem6", "sem6_gpi", "sem 6 gpi"],
    "cgpi": ["cgpi", "c_gpi"],
    "gcgpi": ["gcgpi", "g_cgpi"],
    "remark": ["remark", "remarks"],
    "result_status": ["result_status", "status", "result"],
}

REQUIRED_FIELDS = ["name", "prn", "seat_no"]
