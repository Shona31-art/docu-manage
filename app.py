"""
app.py
DocuManage — Secure Document Management System
Run with: streamlit run app.py
"""

import os
import streamlit as st
import pandas as pd
from pathlib import Path

import database as db
import auth
import ai_extractor
import documents as documents_module
import users as users_module
import reports_page as reports_module

st.set_page_config(page_title="DocuManage", page_icon=":material/folder:", layout="wide")

db.init_db()

UPLOAD_DIR = Path("uploaded_files")
UPLOAD_DIR.mkdir(exist_ok=True)


# ---------- SESSION STATE INIT ----------
if "user" not in st.session_state:
    st.session_state.user = None


# ---------- HELPERS ----------

ROLE_LABELS = {
    "finance/admin": "Finance / Admin",
    "reviewer":      "Reviewer",
    "manager":       "Manager",
}


def logout():
    st.session_state.user = None


# ---------- LOGIN / SIGNUP SCREEN ----------

def show_login():
    st.markdown("""
    <style>
    .login-wrap {max-width: 400px; margin: 2rem auto;}
    </style>
    """, unsafe_allow_html=True)

    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown("## DocuManage")
        st.caption("Secure document management system")
        st.write("")

        tab_login, tab_signup = st.tabs(["Sign in", "Create account"])

        with tab_login:
            with st.form("login_form"):
                email = st.text_input("Email address")
                password = st.text_input("Password", type="password")
                submitted = st.form_submit_button("Sign in", use_container_width=True)

                if submitted:
                    if not email or not password:
                        st.error("Please enter your email and password.")
                    else:
                        user = auth.login(email, password)
                        if user is None:
                            st.error("Incorrect email or password.")
                        else:
                            st.session_state.user = user
                            st.rerun()

        with tab_signup:
            with st.form("signup_form"):
                company_name = st.text_input(
                    "Company name",
                    help="Use the exact same name as your colleagues to share documents."
                )
                full_name = st.text_input("Full name")
                new_email = st.text_input("Email address", key="signup_email")
                new_password = st.text_input(
                    "Password", type="password", key="signup_pw",
                    help="Minimum 6 characters"
                )
                st.caption("🔒 Password must be at least 6 characters")
                role = st.selectbox(
                    "Role", options=list(ROLE_LABELS.keys()),
                    format_func=lambda r: ROLE_LABELS[r]
                )
                signup_submitted = st.form_submit_button(
                    "Create account", use_container_width=True
                )

                if signup_submitted:
                    if not company_name.strip():
                        st.error("Company name is required.")
                    elif not full_name.strip():
                        st.error("Full name is required.")
                    elif not new_email.strip():
                        st.error("Email address is required.")
                    elif len(new_password) < 6:
                        st.error("Password must be at least 6 characters long.")
                    else:
                        success, message = auth.signup(
                            company_name, new_email, new_password, full_name, role
                        )
                        if success:
                            st.success(message + " Please sign in above.")
                        else:
                            st.error(message)


# ---------- UPLOAD PAGE ----------

def show_upload():
    st.header(":material/upload_file: Upload document")
    st.caption("Only invoices and credit notes are accepted.")

    uploaded_file = st.file_uploader(
        "Choose a file", type=["pdf", "png", "jpg", "jpeg"], key="uploader"
    )

    if uploaded_file is None:
        return

    # Save to a temp path so the AI extractor (which reads from disk) can use it
    temp_path = UPLOAD_DIR / f"_preview_{uploaded_file.name}"
    with open(temp_path, "wb") as f:
        f.write(uploaded_file.getbuffer())

    with st.spinner("Reading document..."):
        extracted = ai_extractor.extract_invoice_data(str(temp_path))

    st.success("Document read. Review and correct the details below before submitting.")

    with st.form("upload_form"):
        document_type = st.selectbox(
            "Document type", ["invoice", "credit_note"],
            index=0 if extracted["document_type"] == "invoice" else 1
        )

        col1, col2 = st.columns(2)
        with col1:
            vendor_name = st.text_input("Vendor name", value=extracted["vendor_name"])
            invoice_number = st.text_input(
                "Invoice / credit note number", value=extracted["invoice_number"]
            )
            invoice_date = st.text_input(
                "Document date", value=extracted["invoice_date"],
                help="As read from the document. Edit if it looks wrong."
            )
        with col2:
            subtotal = st.number_input(
                "Subtotal (R)", min_value=0.0, step=0.01, value=float(extracted["subtotal"])
            )
            vat_amount = st.number_input(
                "VAT amount (R)", min_value=0.0, step=0.01, value=float(extracted["vat_amount"])
            )
            amount = st.number_input(
                "Total amount (R)", min_value=0.0, step=0.01, value=float(extracted["amount"])
            )

        submitted = st.form_submit_button("Submit document", use_container_width=True, type="primary")

        if submitted:
            if not vendor_name or not invoice_number:
                st.error("Vendor name and invoice/credit note number are required.")
                return

            company_id = st.session_state.user["company_id"]

            uploaded_file.seek(0)
            file_hash = db.calculate_file_hash(uploaded_file)

            # --- Duplicate checks, as required by the brief ---
            # 1. Exact file match (same file uploaded twice)
            file_dup = db.find_duplicate_file(file_hash, company_id)
            # 2. Invoice number match (primary check)
            invoice_dup = db.find_duplicate_invoice_number(invoice_number, company_id)
            # 3. Vendor + amount match (secondary validation)
            vendor_amount_dup = db.find_duplicate_vendor_amount(vendor_name, amount, company_id)

            is_dup = bool(file_dup or invoice_dup or vendor_amount_dup)

            # Save the real file to permanent storage
            final_path = UPLOAD_DIR / f"{company_id}_{invoice_number or 'doc'}_{uploaded_file.name}"
            with open(final_path, "wb") as f:
                uploaded_file.seek(0)
                f.write(uploaded_file.getbuffer())

            doc_id = db.create_document(
                file_name=uploaded_file.name,
                file_path=str(final_path),
                file_hash=file_hash,
                document_type=document_type,
                vendor_name=vendor_name,
                invoice_number=invoice_number,
                invoice_date=invoice_date,
                subtotal=subtotal,
                vat_amount=vat_amount,
                amount=amount,
                uploaded_by=st.session_state.user["id"],
                company_id=company_id,
                is_duplicate=is_dup,
            )

            if is_dup:
                reasons = []
                if file_dup:
                    reasons.append("identical file already uploaded")
                if invoice_dup:
                    reasons.append(f"invoice number **{invoice_number}** already exists")
                if vendor_amount_dup:
                    reasons.append(f"same vendor and amount (R{amount:.2f}) already recorded")
                st.warning(
                    "Duplicate detected — " + "; ".join(reasons) + ". "
                    "This document has been flagged and will not enter the approval workflow."
                )
            else:
                st.success("Document uploaded and sent for approval.")

            try:
                temp_path.unlink()
            except FileNotFoundError:
                pass


# ---------- MY QUEUE PAGE ----------

def show_queue():
    role = st.session_state.user["role"]
    company_id = st.session_state.user["company_id"]

    if role not in db.ROLE_TO_STEP:
        st.info("Your role does not have approval responsibilities.")
        return

    my_step = db.ROLE_TO_STEP[role]
    st.info(
        f"You handle **Step {my_step} — {ROLE_LABELS[role]}**. "
        f"Only documents ready for your step appear here."
    )

    all_docs = db.get_company_documents(company_id)
    if all_docs.empty:
        st.info("No documents in the system yet.")
        return

    queue_ids = []
    for doc_id in all_docs["id"]:
        approvals = db.get_document_approvals(doc_id)
        my_row = approvals[approvals["role_required"].str.lower() == role]
        if my_row.empty or my_row.iloc[0]["status"].lower() != "pending":
            continue
        earlier = approvals[approvals["step"] < my_step]
        if not earlier.empty and not (earlier["status"].str.lower() == "approved").all():
            continue
        queue_ids.append(doc_id)

    queue = all_docs[all_docs["id"].isin(queue_ids)]

    if queue.empty:
        st.success("Your queue is empty — nothing needs your action right now.")
        return

    for _, doc in queue.iterrows():
        with st.container(border=True):
            col1, col2 = st.columns([3, 1])
            with col1:
                st.markdown(f"**{doc['file_name']}**")
                st.caption(f"{doc['vendor_name']} · #{doc['invoice_number']}")
            with col2:
                st.markdown(f"R{doc['amount']:.2f}")
    st.caption("Open the **Documents** page to review and act on these.")


# ---------- MAIN DASHBOARD ----------

def show_dashboard():
    user = st.session_state.user
    role = user["role"]
    company_name = db.get_company_name(user["company_id"])

    with st.sidebar:
        st.markdown(f"**{user['full_name']}**")
        st.caption(f"{ROLE_LABELS.get(role, role)}" + (f" · {company_name}" if company_name else ""))
        st.divider()

        pages = ["Documents", "Upload document", "Reports"]
        if role in db.ROLE_TO_STEP:
            pages.insert(0, "My queue")
        if role == "finance/admin":
            pages.append("Users & roles")

        page = st.radio("Navigate", pages, label_visibility="collapsed")

        st.divider()
        if st.button(":material/logout: Sign out", use_container_width=True):
            logout()
            st.rerun()

    if page == "My queue":
        st.title("My approval queue")
        show_queue()
    elif page == "Documents":
        documents_module.documents_page()
    elif page == "Upload document":
        show_upload()
    elif page == "Reports":
        reports_module.reports_page()
    elif page == "Users & roles":
        users_module.users_page()


# ---------- ENTRY POINT ----------

if st.session_state.user is None:
    show_login()
else:
    show_dashboard()
