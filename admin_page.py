import io
import zipfile
from datetime import date, timedelta

import pandas as pd
import streamlit as st

from db import csv_bytes, df_query, dump_db, excel_bytes, get_conn, log_action
from pdf_gen import generate_letter


def render(user):
    st.header("Admin Dashboard")
    base = df_query(
        """
        SELECT er.id request_id, er.status, er.created_at, er.updated_at, er.admin_comment,
               s.name student_name, s.prn, s.seat_no, s.cgpi, s.remark, s.result_status,
               se.name session_name, e.exam_name, e.program_code, l.file_path
        FROM edit_requests er
        JOIN students s ON s.id=er.student_id
        JOIN sessions se ON se.id=s.session_id
        JOIN exams e ON e.id=s.exam_id
        LEFT JOIN letters l ON l.request_id=er.id
        WHERE er.faculty=?
        ORDER BY er.id DESC
        """,
        (user["faculty"],),
    )
    if base.empty:
        st.info("No requests")
        return
    today = date.today()
    c1, c2 = st.columns(2)
    if c1.button("Today's report"):
        st.session_state.admin_from = today
        st.session_state.admin_to = today
    if c2.button("Yesterday's report"):
        y = today - timedelta(days=1)
        st.session_state.admin_from = y
        st.session_state.admin_to = y
    d_from = st.date_input("From", value=st.session_state.get("admin_from", today - timedelta(days=30)))
    d_to = st.date_input("To", value=st.session_state.get("admin_to", today))
    sess = st.selectbox("Session", ["ALL"] + sorted(base.session_name.unique().tolist()))
    exam = st.selectbox("Exam", ["ALL"] + sorted(base.exam_name.unique().tolist()))
    prn = st.text_input("PRN")
    seat = st.text_input("Seat")
    status = st.selectbox("Status", ["ALL", "SUBMITTED_BY_CLERK", "ADMIN_APPROVED", "ADMIN_REJECTED", "ADMIN_SUGGESTED_EDIT"])

    filt = base.copy()
    filt = filt[(pd.to_datetime(filt.created_at).dt.date >= d_from) & (pd.to_datetime(filt.created_at).dt.date <= d_to)]
    if sess != "ALL": filt = filt[filt.session_name == sess]
    if exam != "ALL": filt = filt[filt.exam_name == exam]
    if prn: filt = filt[filt.prn.astype(str).str.contains(prn)]
    if seat: filt = filt[filt.seat_no.astype(str).str.contains(seat)]
    if status != "ALL": filt = filt[filt.status == status]

    st.dataframe(filt, use_container_width=True)
    st.download_button("CSV export", csv_bytes(filt), "admin_filtered.csv", "text/csv")
    st.download_button("Excel export", excel_bytes(filt), "admin_filtered.xlsx")

    rid = st.selectbox("Request id", filt.request_id.tolist() if not filt.empty else [])
    comment = st.text_area("Admin comment")
    c1, c2, c3 = st.columns(3)

    def act(new_status):
        row = filt[filt.request_id == rid].iloc[0].to_dict()
        with get_conn() as conn:
            conn.execute("UPDATE edit_requests SET status=?, admin_comment=?, admin_id=?, updated_at=CURRENT_TIMESTAMP WHERE id=?", (new_status, comment, user["id"], rid))
            if new_status == "ADMIN_APPROVED":
                pdf = generate_letter(row | {"admin_comment": comment})
                conn.execute("INSERT OR REPLACE INTO letters(request_id,file_path) VALUES(?,?)", (rid, pdf))
                conn.execute("INSERT OR IGNORE INTO final_actions(request_id,final_status,updated_by) VALUES(?,?,?)", (rid, "PENDING", user["id"]))
        dump_db()
        log_action(user["username"], f"ADMIN_{new_status.split('_')[1]}", "edit_requests", str(rid), {"comment": comment})
        st.success(f"Updated to {new_status}")

    if c1.button("Approve"):
        act("ADMIN_APPROVED")
    if c2.button("Reject"):
        act("ADMIN_REJECTED")
    if c3.button("Suggest Edit"):
        act("ADMIN_SUGGESTED_EDIT")

    approved = filt[filt.status == "ADMIN_APPROVED"]
    if not approved.empty and st.button("Download bulk PDFs (ZIP)"):
        mem = io.BytesIO()
        with zipfile.ZipFile(mem, "w") as zf:
            for _, r in approved.dropna(subset=["file_path"]).iterrows():
                zf.write(r.file_path)
        st.download_button("Get ZIP", mem.getvalue(), "letters.zip", "application/zip")
