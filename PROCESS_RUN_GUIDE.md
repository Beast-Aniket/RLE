## Process Run Guide

1. Install dependencies globally (no venv required):
   - `pip install -r requirements.txt`
2. Start server:
   - `python app.py`
3. Login as `BEAST/admin123`.
4. CCF setup order:
   - Create users
   - Create session
   - Create/search course (exam+program+faculty)
   - Upload student data for selected session/course
5. Clerk:
   - Keep session selected
   - Search students and submit requests
   - Track status by session
6. Admin:
   - Filter with date calendar
   - Approve/reject/suggest edits
7. Final:
   - Select request IDs by checkbox
   - Export selected data or mark DONE/PENDING
