# University RLE/RPV System (No Streamlit)

Flask + SQLite based result correction system with role-based dashboards.

## Default login
- Username: `BEAST`
- Password: `admin123`
- Role: `CCF`

## Run (works without venv)
1. `pip install -r requirements.txt`
2. `python app.py`
3. Open `http://localhost:8501`

## Highlights
- No Streamlit and no Pillow dependency in this project setup.
- CCF can search/select existing course before upload.
- Clerk sees session-wise request status and has home/back links.
- Admin date filtering uses browser date picker calendar.
- Final member can click-select IDs, export selected CSV/Excel, and bulk update states.
- Faculty scoping is enforced in Clerk/Admin/Final queries.
