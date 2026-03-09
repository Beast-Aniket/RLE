# University RLE/RPV System

Streamlit + SQLite application for result correction workflows with role-based access.

## Default login
- Username: `BEAST`
- Password: `admin123`
- Role: `CCF`

## Run
1. `python -m venv .venv`
2. `source .venv/bin/activate`
3. `pip install -r requirements.txt`
4. `streamlit run app.py`

## Modules
- `app.py` entrypoint/routing
- `db.py` schema bootstrap, dump, audit helpers
- `auth.py` login/session checks
- `ccf_page.py` CCF operations (user/session/exam/upload/audit)
- `clerk_page.py` clerk workflow
- `admin_page.py` admin workflow + PDF generation trigger
- `final_page.py` final member bulk workflow
- `import_config.py` import alias standards
- `pdf_config.py` PDF format standards
- `pdf_gen.py` PDF creation

Artifacts generated at runtime:
- `rle_runtime.db`
- `sql_dump.sql`
- `letters/*.pdf`
