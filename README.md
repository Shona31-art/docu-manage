# DocuManage — Secure Document Management System

Built with: **Python, Streamlit, SQLite (SQL), Pandas, bcrypt, PyMuPDF, ReportLab, OpenPyXL**

## Quick start

```bash
pip install -r requirements.txt
streamlit run app.py
```

Open the URL it prints (usually http://localhost:8501), sign up, and you're in.

## Features

### Authentication
- Secure login with bcrypt password hashing
- Role-based access: Reviewer, Manager, Finance/Admin, Viewer
- Multi-company support — each company only sees their own documents

### Upload (invoices & credit notes only)
- Drag-and-drop PDF, PNG, JPG
- AI auto-extraction: vendor name, invoice number, date, subtotal, VAT, total
- Editable pre-fill — review extracted data before submitting

### Duplicate detection (two layers)
- Exact file hash match (same file uploaded twice)
- Invoice number match against existing records (primary check)
- Vendor + amount secondary validation (catches resubmissions with different filenames)

### 3-step approval workflow
- Step 1: Reviewer → Approve / Reject
- Step 2: Manager → Approve / Reject (unlocks only after Step 1 approved)
- Step 3: Finance/Admin → Final approval (unlocks only after Step 2 approved)
- Any rejection at any step immediately marks the document rejected
- Status tracked: pending / approved / rejected / duplicate

### Reports
- Filter by date range, vendor, status, amount
- Spend summary, vendor analysis, approval status breakdown
- AI-driven insights: trends, top vendors, anomalies, pending alerts
- Export to PDF and Excel

### User management
- Finance/Admin can view all company users
- Update user roles from within the app

## File structure

```
app.py            — main Streamlit app, routing, upload, login
database.py       — all SQL schema and queries (SQLite)
auth.py           — password hashing (bcrypt) and login/signup
documents.py      — documents list with approval actions
users.py          — user management page
reports.py        — reporting, AI insights, PDF/Excel export
ai_extractor.py   — PDF/image text extraction using PyMuPDF + regex
migration.py      — safe schema upgrade runner for existing databases
requirements.txt  — all Python dependencies
.gitignore        — excludes venv, database, uploaded files from Git
```

## Deploying live (free)

1. Push this folder to a new GitHub repository
2. Go to **share.streamlit.io** → sign in with GitHub
3. New app → select your repo → main file: `app.py` → Deploy

> **Note:** Streamlit Community Cloud's free tier uses ephemeral storage —
> the SQLite database and uploaded files reset when the app sleeps or redeploys.
> For persistent storage, swap `database.py` to use a hosted Postgres database
> (e.g. free Supabase tier). The SQL logic stays nearly identical.

## Requirements vs built

| Requirement | Status |
|---|---|
| Secure login with role-based access | ✅ |
| Admin / Approver / Viewer roles | ✅ (Reviewer, Manager, Finance/Admin, Viewer) |
| Upload page — invoices & credit notes only | ✅ |
| AI auto-extraction (vendor, date, amount, VAT, invoice #) | ✅ |
| 3-step approval workflow | ✅ |
| Status tracking: pending / approved / rejected | ✅ |
| Duplicate detection — invoice number match | ✅ |
| Duplicate detection — vendor + amount secondary validation | ✅ |
| Reports — filter by date, vendor, status, amount | ✅ |
| Spend summary | ✅ |
| Vendor analysis | ✅ |
| Tax/VAT report | ✅ |
| AI insights — trends, anomalies, spending insights | ✅ |
| Export PDF | ✅ |
| Export Excel | ✅ |
| Multi-company isolation | ✅ (bonus — not in brief) |
| File hash duplicate detection | ✅ (bonus — not in brief) |
| User role management | ✅ (bonus — not in brief) |
