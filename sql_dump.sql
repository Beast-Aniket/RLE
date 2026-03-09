PRAGMA foreign_keys=OFF;
BEGIN TRANSACTION;
CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password TEXT NOT NULL,
    role TEXT NOT NULL CHECK(role IN ('CCF','CLERK','ADMIN','FINAL')),
    faculty TEXT,
    active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
INSERT INTO users VALUES(1,'BEAST','admin123','CCF',NULL,1,'2026-03-09 09:03:08');
CREATE TABLE sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL,
    created_by INTEGER,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE exams (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    exam_name TEXT NOT NULL,
    program_code TEXT NOT NULL,
    faculty TEXT NOT NULL,
    UNIQUE(exam_name, program_code, faculty)
);
CREATE TABLE students (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL,
    exam_id INTEGER NOT NULL,
    faculty TEXT NOT NULL,
    name TEXT NOT NULL,
    prn TEXT NOT NULL,
    seat_no TEXT NOT NULL,
    sex TEXT,
    sem1_gpi REAL,
    sem2_gpi REAL,
    sem3_gpi REAL,
    sem4_gpi REAL,
    sem5_gpi REAL,
    sem6_gpi REAL,
    cgpi REAL,
    gcgpi REAL,
    remark TEXT,
    result_status TEXT,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(session_id, exam_id, prn, seat_no),
    FOREIGN KEY(session_id) REFERENCES sessions(id),
    FOREIGN KEY(exam_id) REFERENCES exams(id)
);
CREATE TABLE edit_requests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER NOT NULL,
    clerk_id INTEGER NOT NULL,
    faculty TEXT NOT NULL,
    status TEXT NOT NULL,
    clerk_comment TEXT,
    admin_comment TEXT,
    suggested_payload TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    admin_id INTEGER,
    FOREIGN KEY(student_id) REFERENCES students(id),
    FOREIGN KEY(clerk_id) REFERENCES users(id),
    FOREIGN KEY(admin_id) REFERENCES users(id)
);
CREATE TABLE letters (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    request_id INTEGER UNIQUE NOT NULL,
    file_path TEXT NOT NULL,
    generated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(request_id) REFERENCES edit_requests(id)
);
CREATE TABLE final_actions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    request_id INTEGER UNIQUE NOT NULL,
    final_status TEXT NOT NULL DEFAULT 'PENDING' CHECK(final_status IN ('PENDING','DONE','QUERY')),
    updated_by INTEGER,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(request_id) REFERENCES edit_requests(id),
    FOREIGN KEY(updated_by) REFERENCES users(id)
);
CREATE TABLE audit_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    actor TEXT,
    action TEXT NOT NULL,
    entity_type TEXT,
    entity_id TEXT,
    details TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
DELETE FROM sqlite_sequence;
INSERT INTO sqlite_sequence VALUES('users',1);
COMMIT;
