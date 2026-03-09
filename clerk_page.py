import streamlit as st

from db import df_query, get_conn, log_action


def _recalc(student):
    vals = [student.get(f"sem{i}_gpi") for i in range(1, 7)]
    vals = [v for v in vals if v is not None]
    return round(sum(vals) / len(vals), 2) if vals else None


def render(user):
    st.header("Clerk Dashboard")
    sessions = df_query("SELECT id,name FROM sessions ORDER BY name")
    exams = df_query("SELECT id,exam_name,program_code FROM exams WHERE faculty=?", (user["faculty"],))
    if sessions.empty or exams.empty:
        st.info("No session/exam mapped yet")
        return
    sid = st.selectbox("Session", sessions.id.tolist(), format_func=lambda x: sessions[sessions.id == x].iloc[0].name)
    eid = st.selectbox("Exam", exams.id.tolist(), format_func=lambda x: f"{exams[exams.id==x].iloc[0].exam_name} ({exams[exams.id==x].iloc[0].program_code})")
    q = st.text_input("Search PRN or Seat")
    students = df_query(
        "SELECT * FROM students WHERE faculty=? AND session_id=? AND exam_id=? AND (prn LIKE ? OR seat_no LIKE ?)",
        (user["faculty"], sid, eid, f"%{q}%", f"%{q}%"),
    )
    st.dataframe(students[["id", "name", "prn", "seat_no", "remark", "cgpi"]], use_container_width=True)

    if not students.empty:
        stid = st.selectbox("Student id", students.id.tolist())
        s = students[students.id == stid].iloc[0].to_dict()
        cols = st.columns(6)
        updates = {}
        for i in range(1, 7):
            updates[f"sem{i}_gpi"] = cols[i - 1].number_input(f"Sem{i}", value=float(s.get(f"sem{i}_gpi") or 0.0), min_value=0.0, max_value=10.0)
        new_remark = st.text_input("Remark", value=s.get("remark") or "")
        comment = st.text_area("Clerk comment")
        if st.button("Save + Submit to Admin"):
            all_present = all(v > 0 for v in updates.values())
            if all_present and "RLE" in (new_remark or ""):
                new_remark = (new_remark or "").replace("RLE", "").strip()
            new_cgpi = round(sum(updates.values()) / len(updates.values()), 2)
            with get_conn() as conn:
                conn.execute(
                    "UPDATE students SET sem1_gpi=?,sem2_gpi=?,sem3_gpi=?,sem4_gpi=?,sem5_gpi=?,sem6_gpi=?,cgpi=?,remark=?,updated_at=CURRENT_TIMESTAMP WHERE id=?",
                    (updates["sem1_gpi"], updates["sem2_gpi"], updates["sem3_gpi"], updates["sem4_gpi"], updates["sem5_gpi"], updates["sem6_gpi"], new_cgpi, new_remark, stid),
                )
                conn.execute(
                    "INSERT INTO edit_requests(student_id,clerk_id,faculty,status,clerk_comment) VALUES(?,?,?,?,?)",
                    (stid, user["id"], user["faculty"], "SUBMITTED_BY_CLERK", comment),
                )
            log_action(user["username"], "CLERK_SUBMITTED", "edit_requests", str(stid), {"comment": comment})
            st.success("Submitted")

    reqs = df_query("SELECT * FROM edit_requests WHERE clerk_id=? ORDER BY id DESC", (user["id"],))
    st.subheader("My Requests")
    st.dataframe(reqs, use_container_width=True)
