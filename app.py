from __future__ import annotations

import io
import sqlite3
from datetime import date, timedelta
from functools import wraps
from pathlib import Path

import pandas as pd
from dbfread import DBF
from flask import Flask, Response, redirect, render_template_string, request, send_file, session, url_for

from db import DB_PATH, init_db, log_action
from import_config import COLUMN_ALIASES, REQUIRED_FIELDS
from pdf_gen import generate_letter

app = Flask(__name__)
app.secret_key = "rle-secret-key"


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def login_required(role=None):
    def deco(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            user = session.get("user")
            if not user:
                return redirect(url_for("login"))
            if role and user["role"] != role:
                return "Unauthorized", 403
            return fn(*args, **kwargs)

        return wrapper

    return deco


def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    normalized = {c.strip().lower(): c for c in df.columns}
    out = {}
    for target, aliases in COLUMN_ALIASES.items():
        for alias in aliases:
            key = alias.strip().lower()
            if key in normalized:
                out[target] = df[normalized[key]]
                break
    return pd.DataFrame(out)


def calc_cgpi(row):
    vals = [row.get(f"sem{i}_gpi") for i in range(1, 7)]
    vals = [float(v) for v in vals if pd.notna(v) and str(v).strip() != ""]
    return round(sum(vals) / len(vals), 2) if vals else None


def parse_upload(file_storage):
    name = file_storage.filename.lower()
    if name.endswith(".csv"):
        df = pd.read_csv(file_storage)
    elif name.endswith(".xlsx"):
        df = pd.read_excel(file_storage)
    elif name.endswith(".dbf"):
        tmp = Path("/tmp/upload.dbf")
        file_storage.save(tmp)
        df = pd.DataFrame(iter(DBF(tmp, load=True)))
    else:
        raise ValueError("Unsupported file")
    return normalize_columns(df)


@app.route("/")
def home():
    user = session.get("user")
    if not user:
        return redirect(url_for("login"))
    return redirect(url_for(user["role"].lower()))


@app.route("/login", methods=["GET", "POST"])
def login():
    msg = ""
    if request.method == "POST":
        u = request.form["username"].strip()
        p = request.form["password"].strip()
        with get_conn() as conn:
            row = conn.execute("SELECT * FROM users WHERE username=? AND password=? AND active=1", (u, p)).fetchone()
        if row:
            session["user"] = dict(row)
            return redirect(url_for("home"))
        msg = "Invalid credentials"
    return render_template_string("""
    <h2>University RLE/RPV Login</h2><p style='color:red;'>{{msg}}</p>
    <form method='post'>Username <input name='username'> Password <input type='password' name='password'>
    <button>Login</button></form>
    """, msg=msg)


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))


@app.route('/ccf', methods=['GET', 'POST'])
@login_required('CCF')
def ccf():
    note = ""
    action = request.form.get("action")
    user = session["user"]
    with get_conn() as conn:
        if action == "create_user":
            conn.execute("INSERT INTO users(username,password,role,faculty,active) VALUES(?,?,?,?,1)",
                         (request.form['username'], request.form['password'], request.form['role'], request.form.get('faculty') or None))
            log_action(user['username'], 'USER_CREATE', 'users', request.form['username'])
            note = 'User created'
        elif action == "create_session":
            conn.execute("INSERT OR IGNORE INTO sessions(name,created_by) VALUES(?,?)", (request.form['session_name'], user['id']))
            log_action(user['username'], 'SESSION_CREATE', 'sessions', request.form['session_name'])
            note = 'Session saved'
        elif action == "create_exam":
            conn.execute("INSERT OR IGNORE INTO exams(exam_name,program_code,faculty) VALUES(?,?,?)",
                         (request.form['exam_name'], request.form['program_code'], request.form['faculty']))
            log_action(user['username'], 'EXAM_CREATE', 'exams', request.form['exam_name'])
            note = 'Course/exam saved'
        elif action == "upload":
            df = parse_upload(request.files['file'])
            missing = [f for f in REQUIRED_FIELDS if f not in df.columns]
            if missing:
                note = f"Missing fields: {missing}"
            else:
                inserted = skipped = 0
                session_id = int(request.form['session_id'])
                exam_id = int(request.form['exam_id'])
                faculty = request.form['faculty']
                for _, row in df.iterrows():
                    if any(pd.isna(row.get(f)) for f in REQUIRED_FIELDS):
                        skipped += 1
                        continue
                    rec = {f: row.get(f) for f in COLUMN_ALIASES}
                    rec['cgpi'] = rec.get('cgpi') if pd.notna(rec.get('cgpi')) else calc_cgpi(rec)
                    try:
                        conn.execute("""INSERT INTO students(session_id,exam_id,faculty,name,prn,seat_no,sex,sem1_gpi,sem2_gpi,sem3_gpi,sem4_gpi,sem5_gpi,sem6_gpi,cgpi,gcgpi,remark,result_status)
                            VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                            ON CONFLICT(session_id,exam_id,prn,seat_no) DO UPDATE SET
                            name=excluded.name,sex=excluded.sex,sem1_gpi=excluded.sem1_gpi,sem2_gpi=excluded.sem2_gpi,sem3_gpi=excluded.sem3_gpi,
                            sem4_gpi=excluded.sem4_gpi,sem5_gpi=excluded.sem5_gpi,sem6_gpi=excluded.sem6_gpi,cgpi=excluded.cgpi,gcgpi=excluded.gcgpi,
                            remark=excluded.remark,result_status=excluded.result_status,updated_at=CURRENT_TIMESTAMP""",
                                     (session_id, exam_id, faculty, rec.get('name'), str(rec.get('prn')), str(rec.get('seat_no')),
                                      rec.get('sex'), rec.get('sem1_gpi'), rec.get('sem2_gpi'), rec.get('sem3_gpi'), rec.get('sem4_gpi'), rec.get('sem5_gpi'), rec.get('sem6_gpi'), rec.get('cgpi'), rec.get('gcgpi'), rec.get('remark'), rec.get('result_status')))
                        inserted += 1
                    except Exception:
                        skipped += 1
                log_action(user['username'], 'UPLOAD', 'students', exam_id, {'inserted': inserted, 'skipped': skipped})
                note = f"Inserted/updated {inserted}, skipped {skipped}"
        conn.commit()
        sessions = conn.execute("SELECT * FROM sessions ORDER BY id DESC").fetchall()
        exam_search = request.args.get('q', '')
        exams = conn.execute("SELECT * FROM exams WHERE exam_name LIKE ? OR program_code LIKE ? ORDER BY exam_name", (f'%{exam_search}%', f'%{exam_search}%')).fetchall()
        users = conn.execute("SELECT id,username,role,faculty,active FROM users ORDER BY id DESC").fetchall()
    return render_template_string("""
    <a href='/logout'>Logout</a><h2>CCF Dashboard</h2><p>{{note}}</p>
    <h3>Create User</h3><form method='post'><input type='hidden' name='action' value='create_user'>
    Username<input name='username'> Password<input name='password'> Role<select name='role'><option>CLERK</option><option>ADMIN</option><option>FINAL</option></select> Faculty<input name='faculty'><button>Create</button></form>
    <h3>Create Session</h3><form method='post'><input type='hidden' name='action' value='create_session'><input name='session_name'><button>Save</button></form>
    <h3>Add Course/Exam</h3><form method='post'><input type='hidden' name='action' value='create_exam'>Name<input name='exam_name'> Program<input name='program_code'> Faculty<input name='faculty'><button>Save</button></form>
    <h3>Search Course</h3><form method='get'><input name='q' value='{{request.args.get("q","")}}'><button>Search</button></form>
    <h3>Upload Data to Existing Course</h3><form method='post' enctype='multipart/form-data'><input type='hidden' name='action' value='upload'>
    Session<select name='session_id'>{% for s in sessions %}<option value='{{s.id}}'>{{s.name}}</option>{% endfor %}</select>
    Course<select name='exam_id'>{% for e in exams %}<option value='{{e.id}}'>{{e.exam_name}} ({{e.program_code}}) - {{e.faculty}}</option>{% endfor %}</select>
    Faculty<input name='faculty'><input type='file' name='file'><button>Upload</button></form>
    <h3>Users</h3><ul>{% for u in users %}<li>{{u.username}} | {{u.role}} | {{u.faculty}} | active={{u.active}}</li>{% endfor %}</ul>
    """, note=note, sessions=sessions, exams=exams, users=users, request=request)


@app.route('/clerk', methods=['GET', 'POST'])
@login_required('CLERK')
def clerk():
    user = session['user']
    msg = ''
    with get_conn() as conn:
        if request.method == 'POST':
            action = request.form.get('action')
            if action == 'set_session':
                session['clerk_session_id'] = request.form['session_id']
                return redirect(url_for('clerk'))
            if action == 'submit_request':
                student_id = int(request.form['student_id'])
                conn.execute("INSERT INTO edit_requests(student_id,clerk_id,faculty,status,clerk_comment) VALUES(?,?,?,?,?)",
                             (student_id, user['id'], user['faculty'], 'SUBMITTED_BY_CLERK', request.form.get('comment','')))
                log_action(user['username'], 'CLERK_SUBMIT', 'edit_requests', student_id)
                msg = 'Submitted'
            conn.commit()
        sess = conn.execute("SELECT * FROM sessions ORDER BY id DESC").fetchall()
        selected = session.get('clerk_session_id') or (sess[0]['id'] if sess else None)
        session['clerk_session_id'] = selected
        exam_rows = conn.execute("SELECT * FROM exams WHERE faculty=? ORDER BY exam_name", (user['faculty'],)).fetchall()
        exam_id = request.args.get('exam_id', type=int) or (exam_rows[0]['id'] if exam_rows else None)
        q = request.args.get('q', '')
        students = []
        if selected and exam_id:
            students = conn.execute("SELECT * FROM students WHERE faculty=? AND session_id=? AND exam_id=? AND (prn LIKE ? OR seat_no LIKE ?)",
                                    (user['faculty'], selected, exam_id, f'%{q}%', f'%{q}%')).fetchall()
        stats = conn.execute("""SELECT s.name session_name, r.status, count(*) c FROM edit_requests r
            JOIN students st ON st.id=r.student_id JOIN sessions s ON s.id=st.session_id
            WHERE r.clerk_id=? GROUP BY s.name,r.status ORDER BY s.name""", (user['id'],)).fetchall()
    return render_template_string("""
    <a href='/'>Home</a> | <a href='/logout'>Logout</a><h2>Clerk Dashboard ({{user.faculty}})</h2><p>{{msg}}</p>
    <h3>Work Status by Session</h3><ul>{% for x in stats %}<li><a href='/clerk?session_name={{x.session_name}}'>{{x.session_name}}</a> - {{x.status}}: {{x.c}}</li>{% endfor %}</ul>
    <form method='post'><input type='hidden' name='action' value='set_session'>Session<select name='session_id'>{% for s in sess %}<option value='{{s.id}}' {% if s.id==selected %}selected{% endif %}>{{s.name}}</option>{% endfor %}</select><button>Keep Session</button></form>
    <form method='get'>Exam<select name='exam_id'>{% for e in exam_rows %}<option value='{{e.id}}' {% if e.id==exam_id %}selected{% endif %}>{{e.exam_name}}({{e.program_code}})</option>{% endfor %}</select> PRN/Seat <input name='q' value='{{request.args.get("q","")}}'><button>Search</button></form>
    <table border=1><tr><th>ID</th><th>Name</th><th>PRN</th><th>Seat</th><th>Remark</th><th>Action</th></tr>
    {% for s in students %}<tr><td>{{s.id}}</td><td>{{s.name}}</td><td>{{s.prn}}</td><td>{{s.seat_no}}</td><td>{{s.remark}}</td><td><form method='post'><input type='hidden' name='action' value='submit_request'><input type='hidden' name='student_id' value='{{s.id}}'><input name='comment'><button>Submit</button></form></td></tr>{% endfor %}
    </table>
    """, user=user, msg=msg, sess=sess, selected=selected, exam_rows=exam_rows, exam_id=exam_id, students=students, stats=stats, request=request)


@app.route('/admin', methods=['GET', 'POST'])
@login_required('ADMIN')
def admin():
    user = session['user']
    msg = ''
    with get_conn() as conn:
        if request.method == 'POST':
            rid = int(request.form['request_id'])
            status = request.form['status']
            comment = request.form.get('admin_comment', '')
            conn.execute("UPDATE edit_requests SET status=?,admin_comment=?,admin_id=?,updated_at=CURRENT_TIMESTAMP WHERE id=? AND faculty=?",
                         (status, comment, user['id'], rid, user['faculty']))
            if status == 'ADMIN_APPROVED':
                row = conn.execute("""SELECT r.id request_id,se.name session_name,e.exam_name,e.program_code,st.name student_name,st.prn,st.seat_no,st.result_status,st.cgpi,st.remark,? admin_comment
                FROM edit_requests r JOIN students st ON st.id=r.student_id JOIN sessions se ON se.id=st.session_id JOIN exams e ON e.id=st.exam_id WHERE r.id=?""", (comment, rid)).fetchone()
                pdf = generate_letter(dict(row))
                conn.execute("INSERT OR REPLACE INTO letters(request_id,file_path) VALUES(?,?)", (rid, pdf))
                conn.execute("INSERT OR IGNORE INTO final_actions(request_id,final_status,updated_by) VALUES(?,?,?)", (rid, 'PENDING', user['id']))
            log_action(user['username'], status, 'edit_requests', rid)
            conn.commit()
            msg = 'Updated'

        start = request.args.get('start') or (date.today() - timedelta(days=30)).isoformat()
        end = request.args.get('end') or date.today().isoformat()
        status_f = request.args.get('status', '')
        sql = """SELECT r.*,st.prn,st.seat_no,se.name session_name,e.exam_name,e.program_code FROM edit_requests r
            JOIN students st ON st.id=r.student_id JOIN sessions se ON se.id=st.session_id JOIN exams e ON e.id=st.exam_id
            WHERE r.faculty=? AND date(r.created_at) BETWEEN ? AND ?"""
        params = [user['faculty'], start, end]
        if status_f:
            sql += " AND r.status=?"
            params.append(status_f)
        rows = conn.execute(sql + " ORDER BY r.id DESC", params).fetchall()
    return render_template_string("""
    <a href='/'>Home</a> | <a href='/logout'>Logout</a><h2>Admin Dashboard ({{user.faculty}})</h2><p>{{msg}}</p>
    <form method='get'>Start <input type='date' name='start' value='{{start}}'> End <input type='date' name='end' value='{{end}}'>
    Status<select name='status'><option value=''>All</option><option>SUBMITTED_BY_CLERK</option><option>ADMIN_APPROVED</option><option>ADMIN_REJECTED</option><option>ADMIN_SUGGESTED_EDIT</option></select>
    <button>Filter</button></form>
    <table border=1><tr><th>ID</th><th>PRN</th><th>Session</th><th>Exam</th><th>Status</th><th>Action</th></tr>
    {% for r in rows %}<tr><td>{{r.id}}</td><td>{{r.prn}}</td><td>{{r.session_name}}</td><td>{{r.exam_name}}</td><td>{{r.status}}</td><td>
    <form method='post'><input type='hidden' name='request_id' value='{{r.id}}'><input name='admin_comment'>
    <button name='status' value='ADMIN_APPROVED'>Approve</button><button name='status' value='ADMIN_REJECTED'>Reject</button><button name='status' value='ADMIN_SUGGESTED_EDIT'>Suggest</button></form>
    </td></tr>{% endfor %}</table>
    """, user=user, rows=rows, start=start, end=end, msg=msg)


@app.route('/final', methods=['GET', 'POST'])
@login_required('FINAL')
def final():
    user = session['user']
    msg = ''
    with get_conn() as conn:
        if request.method == 'POST':
            ids = [int(x) for x in request.form.getlist('request_ids')]
            if request.form.get('action') in {'DONE', 'PENDING'}:
                for rid in ids:
                    conn.execute("UPDATE final_actions SET final_status=?,updated_by=?,updated_at=CURRENT_TIMESTAMP WHERE request_id=?",
                                 (request.form['action'], user['id'], rid))
                log_action(user['username'], 'FINAL_BULK_UPDATE', 'final_actions', ','.join(map(str, ids)), {'status': request.form['action']})
                conn.commit()
                msg = f"Updated {len(ids)}"
            elif request.form.get('action') == 'export_csv':
                return export_final(conn, ids, 'csv')
            elif request.form.get('action') == 'export_xlsx':
                return export_final(conn, ids, 'xlsx')

        where = " WHERE r.status='ADMIN_APPROVED' "
        params = []
        if user.get('faculty'):
            where += " AND r.faculty=?"
            params.append(user['faculty'])
        rows = conn.execute(f"""SELECT r.id request_id,se.name session_name,e.exam_name,st.prn,st.seat_no,fa.final_status,l.file_path
            FROM edit_requests r JOIN students st ON st.id=r.student_id JOIN sessions se ON se.id=st.session_id JOIN exams e ON e.id=st.exam_id
            LEFT JOIN final_actions fa ON fa.request_id=r.id LEFT JOIN letters l ON l.request_id=r.id {where} ORDER BY r.id DESC""", params).fetchall()
    return render_template_string("""
    <a href='/'>Home</a> | <a href='/logout'>Logout</a><h2>Final Generator</h2><p>{{msg}}</p>
    <form method='post'><table border=1><tr><th>Select</th><th>ID</th><th>Session</th><th>Exam</th><th>PRN</th><th>Status</th><th>PDF</th></tr>
    {% for r in rows %}<tr><td><input type='checkbox' name='request_ids' value='{{r.request_id}}'></td><td>{{r.request_id}}</td><td>{{r.session_name}}</td><td>{{r.exam_name}}</td><td>{{r.prn}}</td><td>{{r.final_status or 'PENDING'}}</td><td>{{r.file_path or ''}}</td></tr>{% endfor %}</table>
    <button name='action' value='DONE'>Mark DONE</button><button name='action' value='PENDING'>Mark PENDING</button><button name='action' value='export_csv'>Download CSV</button><button name='action' value='export_xlsx'>Download Excel</button></form>
    """, rows=rows, msg=msg)


def export_final(conn, ids, fmt):
    if not ids:
        ids = [-1]
    qmarks = ','.join(['?'] * len(ids))
    df = pd.read_sql_query(f"SELECT * FROM final_actions WHERE request_id IN ({qmarks})", conn, params=ids)
    if fmt == 'csv':
        return Response(df.to_csv(index=False), mimetype='text/csv', headers={'Content-Disposition': 'attachment; filename=final.csv'})
    bio = io.BytesIO()
    df.to_excel(bio, index=False)
    bio.seek(0)
    return send_file(bio, as_attachment=True, download_name='final.xlsx')


if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=8501, debug=False)
