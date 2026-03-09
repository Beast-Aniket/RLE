import streamlit as st

from db import csv_bytes, df_query, dump_db, excel_bytes, get_conn, log_action


def render(user):
    st.header("Final Member Dashboard")
    q = df_query(
        """
        SELECT fa.id as final_id, fa.final_status, er.id request_id, er.updated_at action_date,
               se.name session_name, e.exam_name, e.program_code,
               s.name student_name, s.prn, s.seat_no, l.file_path
        FROM final_actions fa
        JOIN edit_requests er ON er.id=fa.request_id
        JOIN students s ON s.id=er.student_id
        JOIN sessions se ON se.id=s.session_id
        JOIN exams e ON e.id=s.exam_id
        LEFT JOIN letters l ON l.request_id=er.id
        WHERE er.status='ADMIN_APPROVED'
        ORDER BY fa.id DESC
        """
    )
    if q.empty:
        st.info("No approved items")
        return
    sess = st.selectbox("Session", ["ALL"] + sorted(q.session_name.unique().tolist()))
    exam = st.selectbox("Exam", ["ALL"] + sorted(q.exam_name.unique().tolist()))
    day = st.date_input("Date")
    filt = q.copy()
    if sess != "ALL": filt = filt[filt.session_name == sess]
    if exam != "ALL": filt = filt[filt.exam_name == exam]
    filt = filt[filt.action_date.str[:10] == str(day)] if day else filt
    st.dataframe(filt, use_container_width=True)
    st.download_button("CSV", csv_bytes(filt), "final.csv")
    st.download_button("Excel", excel_bytes(filt), "final.xlsx")

    all_toggle = st.checkbox("Select all filtered")
    options = filt.final_id.tolist()
    selected = options if all_toggle else st.multiselect("Select entries", options)
    c1, c2 = st.columns(2)
    if c1.button("Mark DONE") and selected:
        with get_conn() as conn:
            conn.executemany("UPDATE final_actions SET final_status='DONE', updated_by=?, updated_at=CURRENT_TIMESTAMP WHERE id=?", [(user["id"], x) for x in selected])
        dump_db()
        log_action(user["username"], "FINAL_DONE_BULK", "final_actions", ",".join(map(str, selected)))
    if c2.button("Mark PENDING") and selected:
        with get_conn() as conn:
            conn.executemany("UPDATE final_actions SET final_status='PENDING', updated_by=?, updated_at=CURRENT_TIMESTAMP WHERE id=?", [(user["id"], x) for x in selected])
        dump_db()
        log_action(user["username"], "FINAL_PENDING_BULK", "final_actions", ",".join(map(str, selected)))

    st.subheader("PDF Access")
    for _, r in filt.dropna(subset=["file_path"]).iterrows():
        st.write(f"Request {r.request_id}: {r.file_path}")
