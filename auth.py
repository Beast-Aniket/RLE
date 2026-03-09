import streamlit as st
from db import get_conn


def login_box():
    st.subheader("Login")
    username = st.text_input("Username")
    password = st.text_input("Password", type="password")
    if st.button("Login"):
        with get_conn() as conn:
            row = conn.execute(
                "SELECT * FROM users WHERE username=? AND password=? AND active=1", (username, password)
            ).fetchone()
        if row:
            st.session_state.user = dict(row)
            st.success("Logged in")
            st.rerun()
        st.error("Invalid credentials")


def require_login():
    return st.session_state.get("user")
