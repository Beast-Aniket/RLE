import streamlit as st

import admin_page
import ccf_page
import clerk_page
import final_page
from auth import login_box, require_login
from db import init_db

st.set_page_config(page_title="University RLE/RPV", layout="wide")
init_db()

st.title("UNIVERSITY RLE-RPV SYSTEM")
user = require_login()
if not user:
    login_box()
    st.stop()

with st.sidebar:
    st.write(f"Logged in as: {user['username']} ({user['role']})")
    if st.button("Logout"):
        st.session_state.clear()
        st.rerun()

if user["role"] == "CCF":
    ccf_page.render(user)
elif user["role"] == "CLERK":
    clerk_page.render(user)
elif user["role"] == "ADMIN":
    admin_page.render(user)
elif user["role"] == "FINAL":
    final_page.render(user)
else:
    st.error("Unknown role")
