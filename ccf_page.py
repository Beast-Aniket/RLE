import pandas as pd
import streamlit as st
from dbfread import DBF

from db import csv_bytes, df_query, dump_db, get_conn, log_action
from import_config import COLUMN_ALIASES, REQUIRED_FIELDS


def _normalize_columns(df: pd.DataFrame):
    rename = {}
    lowmap = {c.lower().strip(): c for c in df.columns}
    for tgt, aliases in COLUMN_ALIASES.items():
        for a in aliases:
            if a.lower() in lowmap:
                rename[lowmap[a.lower()]] = tgt
                break
    return df.rename(columns=rename)


def _safe_float(v):
    try:
        if v in (None, ""):
            return None
        return float(v)
    except Exception:
        return None


def _calc_cgpi(row):
    vals = [row.get(f"sem{i}_gpi") for i in range(1, 7)]
    vals = [v for v in vals if v is not None]
    return round(sum(vals) / len(vals), 2) if vals else None


def render(user):
    st.header("CCF Dashboard")

    with st.expander("User Management", expanded=True):
        with st.form("create_user"):
            u = st.text_input("Username")
            p = st.text_input("Password")
            role = st.selectbox("Role", ["CLERK", "ADMIN", "FINAL"])
            faculty = st.text_input("Faculty (optional)")
            if st.form_submit_button("Create User") and u and p:
                with get_conn() as conn:
                    conn.execute(
                        "INSERT INTO users(username,password,role,faculty,active) VALUES(?,?,?,?,1)",
                        (u, p, role, faculty or None),
                    )
                log_action(user["username"], "USER_CREATED", "users", u, {"role": role, "faculty": faculty})
                st.success("Created")

        users = df_query("SELECT id,username,role,faculty,active FROM users")
        st.dataframe(users, use_container_width=True)
        uid = st.selectbox("Select user id", [None] + users["id"].tolist())
        if uid:
            target = users[users["id"] == uid].iloc[0]
            new_pass = st.text_input("New password")
            new_role = st.selectbox("New role", ["CCF", "CLERK", "ADMIN", "FINAL"], index=["CCF", "CLERK", "ADMIN", "FINAL"].index(target["role"]))
            new_fac = st.text_input("New faculty", value=target["faculty"] or "")
            active = st.checkbox("Active", value=bool(target["active"]))
            c1, c2, c3 = st.columns(3)
            if c1.button("Update user"):
                with get_conn() as conn:
                    if target["username"] == "BEAST" and new_role != "CCF":
                        st.error("BEAST must remain CCF")
                    else:
                        conn.execute(
                            "UPDATE users SET password=COALESCE(NULLIF(?,''),password), role=?, faculty=?, active=? WHERE id=?",
                            (new_pass, new_role, new_fac or None, int(active), uid),
                        )
                        log_action(user["username"], "USER_UPDATED", "users", str(uid), {"role": new_role, "active": active})
                        st.success("Updated")
            if c2.button("Disable"):
                with get_conn() as conn:
                    conn.execute("UPDATE users SET active=0 WHERE id=?", (uid,))
                log_action(user["username"], "USER_DISABLED", "users", str(uid))
            if c3.button("Delete"):
                if target["username"] == "BEAST":
                    st.error("Cannot delete BEAST")
                else:
                    with get_conn() as conn:
                        conn.execute("DELETE FROM users WHERE id=?", (uid,))
                    log_action(user["username"], "USER_DELETED", "users", str(uid))

    with st.expander("Session & Exam Management", expanded=True):
        s = st.text_input("New session")
        if st.button("Create session") and s:
            with get_conn() as conn:
                conn.execute("INSERT OR IGNORE INTO sessions(name,created_by) VALUES(?,?)", (s, user["id"]))
            log_action(user["username"], "SESSION_CREATED", "sessions", s)

        e1, e2, e3 = st.columns(3)
        exam_name = e1.text_input("Exam name")
        pcode = e2.text_input("Program code")
        fac = e3.text_input("Faculty")
        if st.button("Create exam") and exam_name and pcode and fac:
            with get_conn() as conn:
                conn.execute("INSERT OR IGNORE INTO exams(exam_name,program_code,faculty) VALUES(?,?,?)", (exam_name, pcode, fac))
            log_action(user["username"], "EXAM_CREATED", "exams", f"{exam_name}-{pcode}", {"faculty": fac})

        search = st.text_input("Search exam")
        exams = df_query(
            "SELECT * FROM exams WHERE exam_name LIKE ? OR program_code LIKE ? ORDER BY exam_name",
            (f"%{search}%", f"%{search}%"),
        ) if search else df_query("SELECT * FROM exams ORDER BY exam_name")
        st.dataframe(exams, use_container_width=True)

    with st.expander("Upload Student Results", expanded=True):
        sessions = df_query("SELECT id,name FROM sessions ORDER BY name")
        faculties = sorted([x for x in df_query("SELECT DISTINCT faculty FROM exams WHERE faculty IS NOT NULL")['faculty'].dropna().tolist()])
        s_id = st.selectbox("Session", sessions["id"].tolist(), format_func=lambda x: sessions[sessions.id == x].iloc[0]["name"] if len(sessions) else "") if len(sessions) else None
        fac_sel = st.selectbox("Faculty", faculties) if faculties else None
        exam_opts = df_query("SELECT * FROM exams WHERE faculty=?", (fac_sel,)) if fac_sel else pd.DataFrame()
        opt = exam_opts.apply(lambda r: f"{r.exam_name} ({r.program_code})", axis=1).tolist() if len(exam_opts) else []
        picked = st.selectbox("Exam", ["<Create New>"] + opt)
        if picked == "<Create New>":
            ne = st.text_input("New exam name (upload)")
            np = st.text_input("New program code (upload)")
            if st.button("Create exam for upload") and ne and np and fac_sel:
                with get_conn() as conn:
                    conn.execute("INSERT OR IGNORE INTO exams(exam_name,program_code,faculty) VALUES(?,?,?)", (ne, np, fac_sel))
                st.success("Exam created; reselect from dropdown")
        file = st.file_uploader("Upload csv/xlsx/dbf", type=["csv", "xlsx", "dbf"])
        if st.button("Process Upload") and file and s_id and fac_sel and picked != "<Create New>":
            if file.name.endswith(".csv"):
                df = pd.read_csv(file)
            elif file.name.endswith(".xlsx"):
                df = pd.read_excel(file)
            else:
                from tempfile import NamedTemporaryFile
                with NamedTemporaryFile(delete=False, suffix=".dbf") as tmp:
                    tmp.write(file.getbuffer())
                    rows = list(DBF(tmp.name, load=True))
                df = pd.DataFrame(rows)
            df = _normalize_columns(df)
            for col in [f"sem{i}_gpi" for i in range(1, 7)] + ["cgpi", "gcgpi"]:
                if col in df.columns:
                    df[col] = df[col].map(_safe_float)
            inserted = skipped = 0
            ex = exam_opts.iloc[opt.index(picked)]
            with get_conn() as conn:
                for _, r in df.iterrows():
                    if any(pd.isna(r.get(req)) or str(r.get(req)).strip() == "" for req in REQUIRED_FIELDS):
                        skipped += 1
                        continue
                    vals = {k: r.get(k) for k in ["name", "prn", "seat_no", "sex", "remark", "result_status", "gcgpi"]}
                    for i in range(1, 7):
                        vals[f"sem{i}_gpi"] = _safe_float(r.get(f"sem{i}_gpi"))
                    vals["cgpi"] = _safe_float(r.get("cgpi")) or _calc_cgpi(vals)
                    conn.execute(
                        """
                        INSERT INTO students(session_id,exam_id,faculty,name,prn,seat_no,sex,sem1_gpi,sem2_gpi,sem3_gpi,sem4_gpi,sem5_gpi,sem6_gpi,cgpi,gcgpi,remark,result_status)
                        VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                        ON CONFLICT(session_id,exam_id,prn,seat_no) DO UPDATE SET
                        name=excluded.name,sex=excluded.sex,sem1_gpi=excluded.sem1_gpi,sem2_gpi=excluded.sem2_gpi,
                        sem3_gpi=excluded.sem3_gpi,sem4_gpi=excluded.sem4_gpi,sem5_gpi=excluded.sem5_gpi,sem6_gpi=excluded.sem6_gpi,
                        cgpi=excluded.cgpi,gcgpi=excluded.gcgpi,remark=excluded.remark,result_status=excluded.result_status,updated_at=CURRENT_TIMESTAMP
                        """,
                        (s_id, int(ex.id), fac_sel, vals["name"], str(vals["prn"]), str(vals["seat_no"]), vals["sex"],
                         vals["sem1_gpi"], vals["sem2_gpi"], vals["sem3_gpi"], vals["sem4_gpi"], vals["sem5_gpi"], vals["sem6_gpi"],
                         vals["cgpi"], vals["gcgpi"], vals["remark"], vals["result_status"]),
                    )
                    inserted += 1
            log_action(user["username"], "UPLOAD_STUDENTS", "students", f"session:{s_id},exam:{int(ex.id)}", {"inserted": inserted, "skipped": skipped})
            dump_db()
            st.success(f"Inserted/updated: {inserted}, Skipped: {skipped}")

    audits = df_query("SELECT * FROM audit_logs ORDER BY id DESC")
    st.download_button("Download audit CSV", csv_bytes(audits), "audit_logs.csv", "text/csv")
