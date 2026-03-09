import io
import json
import sqlite3
from contextlib import closing
from pathlib import Path
from typing import Optional

import pandas as pd

DB_PATH = Path("rle_runtime.db")
SCHEMA_PATH = Path("schema.sql")
DUMP_PATH = Path("sql_dump.sql")


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_conn() as conn:
        conn.executescript(SCHEMA_PATH.read_text())
        conn.execute(
            """
            INSERT OR IGNORE INTO users(username,password,role,faculty,active)
            VALUES ('BEAST','admin123','CCF',NULL,1)
            """
        )
    dump_db()


def dump_db():
    with get_conn() as conn:
        sql = "\n".join(conn.iterdump())
    DUMP_PATH.write_text(sql)


def log_action(actor: str, action: str, entity_type: str = "", entity_id: str = "", details: Optional[dict] = None):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO audit_logs(actor,action,entity_type,entity_id,details) VALUES(?,?,?,?,?)",
            (actor, action, entity_type, str(entity_id) if entity_id else "", json.dumps(details or {})),
        )
    dump_db()


def df_query(sql: str, params=()):
    with get_conn() as conn:
        return pd.read_sql_query(sql, conn, params=params)


def csv_bytes(df: pd.DataFrame) -> bytes:
    return df.to_csv(index=False).encode("utf-8")


def excel_bytes(df: pd.DataFrame) -> bytes:
    bio = io.BytesIO()
    with pd.ExcelWriter(bio, engine="openpyxl") as writer:
        df.to_excel(writer, index=False)
    return bio.getvalue()
