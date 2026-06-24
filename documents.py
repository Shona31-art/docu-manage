"""
documents.py
Compact document list with clear separation, text labels, and all action buttons.
"""

import streamlit as st
from pathlib import Path
import database as db

st.markdown("""
<style>
p {
    font-size: 12px;
}

button {
    font-size: 12px !important;
}

.stMarkdown {
    margin-bottom: -10px;
}

</style>
""", unsafe_allow_html=True)

STEP_ORDER = ["reviewer", "manager", "finance/admin"]
STEP_LABEL = {
    "reviewer":     "Reviewer",
    "manager":      "Manager",
    "finance/admin":"Finance/Admin"
}

STATUS_COLOR = {
    "approved":  "#EAF3DE",
    "pending":   "#FAEEDA",
    "rejected":  "#FCEBEB",
    "duplicate": "#FEF3C7",
}
STATUS_ICON = {
    "approved":  "✅",
    "pending":   "⏳",
    "rejected":  "❌",
    "duplicate": "⚠️",
}


def _safe(val):
    """Return val as string if it's a real value, else empty string."""
    if val is None:
        return ""
    s = str(val).strip()
    return "" if s.lower() in ("nan", "none", "nat", "") else s


def _step_display(status):
    """Return text label matching status — same style as before."""
    if status == "approved":
        return "✅ Approved"
    if status == "rejected":
        return "❌ Rejected"
    if status == "pending":
        return "⏳ Pending"
    return "⚪ Waiting"


def documents_page():

    st.header("📄 Documents")

    company_id = st.session_state.user["company_id"]
    docs = db.get_company_documents(company_id)

    if docs.empty:
        st.info("No documents uploaded yet.")
        return

    if "is_duplicate" not in docs.columns:
        docs["is_duplicate"] = 0

    # ── summary counts ────────────────────────────────────────────────────────
    total     = len(docs)
    pending   = len(docs[docs["status"] == "pending"])
    approved  = len(docs[docs["status"] == "approved"])
    rejected  = len(docs[docs["status"] == "rejected"])
    duplicate = len(docs[docs["status"] == "duplicate"])

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Total",        total)
    c2.metric("⏳ Pending",   pending)
    c3.metric("✅ Approved",  approved)
    c4.metric("❌ Rejected",  rejected)
    c5.metric("⚠️ Duplicate", duplicate)

    st.divider()

    user_role = st.session_state.user["role"].lower()

    for idx, (_, doc) in enumerate(docs.iterrows(), 1):

        status = str(doc.get("status", "pending"))
        bg     = STATUS_COLOR.get(status, "#F9FAFB")
        icon   = STATUS_ICON.get(status, "📄")
        doc_type = str(doc.get("document_type", "invoice")).replace("_"," ").title()

        # ── coloured header bar — compact ─────────────────────────────────────
        st.markdown(
            f'<div style="background:{bg};border-radius:4px 4px 0 0;'
            f'padding:4px 12px;border:1px solid #D1D5DB;border-bottom:none;'
            f'display:flex;justify-content:space-between;align-items:center">'
            f'<small style="font-weight:600">'
            f'{icon} {idx}/{total} &nbsp;—&nbsp; {doc["file_name"]}</small>'
            f'<small style="font-weight:600">{status.upper()}</small></div>',
            unsafe_allow_html=True,
        )

        with st.container(border=True):

            if doc["is_duplicate"]:
                st.caption("⚠️ Duplicate — excluded from approval workflow.")

            # ── compact invoice details — 2 columns, small text ───────────────
            col1, col2 = st.columns(2)
            with col1:
                st.caption(f"**Vendor:** {doc['vendor_name'] or '—'}")
                st.caption(f"**Invoice #:** {doc['invoice_number'] or '—'}")
                st.caption(f"**Date:** {doc['invoice_date'] or '—'}  · {doc_type}")
            with col2:
                st.caption(f"**Subtotal:** R {float(doc['subtotal'] or 0):,.2f}")
                st.caption(f"**VAT:** R {float(doc['vat_amount'] or 0):,.2f}")
                st.caption(f"**Total:** R {float(doc['amount'] or 0):,.2f}")

            st.divider()

            # ── approval workflow — 3 compact columns ─────────────────────────
            st.markdown("**🔄 Approval Workflow**")

            approvals = db.get_document_approvals(doc["id"])
            approved_count = 0
            step_cols = st.columns(3)

            for i, step in enumerate(STEP_ORDER):
                row = approvals[
                    approvals["role_required"].str.lower() == step
                ] if not approvals.empty else None

                step_status = "waiting"
                if row is not None and not row.empty:
                    step_status = row.iloc[0]["status"].lower()

                with step_cols[i]:
                    label = _step_display(step_status)
                    st.markdown(f"{label} **{STEP_LABEL[step]}**")

                    if row is not None and not row.empty:
                        comment  = _safe(row.iloc[0]["comments"])
                        actioned = _safe(row.iloc[0]["actioned_at"])
                        if comment:
                            st.caption(f'"{comment}"')
                        if actioned:
                            st.caption(actioned[:10])

                if step_status == "approved":
                    approved_count += 1

            if approved_count == 3:
                st.success("✅ Document fully approved")
            else:
                st.caption(f"Approval Progress: {approved_count}/3")

            st.divider()

            # ── approval history ──────────────────────────────────────────────
            st.markdown("**📜 Approval History**")
            if not approvals.empty:
                acted = approvals[approvals["status"] != "pending"]
                if not acted.empty:
                    for _, row in acted.iterrows():
                        comment = _safe(row["comments"])
                        suffix  = f" — {comment}" if comment else ""
                        st.write(
                            f"Step {int(row['step'])} — "
                            f"{STEP_LABEL.get(row['role_required'], row['role_required'])}: "
                            f"**{row['status'].upper()}**{suffix}"
                        )
                else:
                    st.info("No approval activity yet")
            else:
                st.info("No approval activity yet")

            st.divider()

            # ── approval action ───────────────────────────────────────────────
            st.markdown("**Approval Action**")

            current = approvals[
                approvals["role_required"].str.lower() == user_role
            ] if not approvals.empty else None

            can_show_action = (
                current is not None
                and not current.empty
                and status == "pending"
            )

            if can_show_action:
                current_status = current.iloc[0]["status"].lower()
                current_step   = int(current.iloc[0]["step"])
                earlier        = approvals[approvals["step"] < current_step]
                earlier_ok     = (
                    earlier.empty
                    or (earlier["status"].str.lower() == "approved").all()
                )
                earlier_rej    = (
                    not earlier.empty
                    and (earlier["status"].str.lower() == "rejected").any()
                )

                if current_status == "pending" and earlier_rej:
                    st.info("This document was rejected at an earlier step.")

                elif current_status == "pending" and not earlier_ok:
                    blocked = STEP_ORDER[
                        int(earlier[
                            earlier["status"].str.lower() != "approved"
                        ].iloc[0]["step"]) - 1
                    ]
                    st.info(
                        f"Waiting on **{STEP_LABEL[blocked]}** to act first. "
                        f"This step unlocks once earlier steps are approved."
                    )

                elif current_status == "pending":
                    comment = st.text_area(
                        "Approval Comment",
                        key=f"comment_{doc['id']}"
                    )
                    approve_col, reject_col = st.columns(2)
                    with approve_col:
                        if st.button("✅ Approve", key=f"approve_{doc['id']}"):
                            db.submit_approval(
                                doc["id"], current_step, user_role,
                                st.session_state.user["id"], "approved", comment
                            )
                            st.success("Document approved")
                            st.rerun()
                    with reject_col:
                        if st.button("❌ Reject", key=f"reject_{doc['id']}"):
                            db.submit_approval(
                                doc["id"], current_step, user_role,
                                st.session_state.user["id"], "rejected", comment
                            )
                            st.warning("Document rejected")
                            st.rerun()

                else:
                    st.info(f"No approval action required")

            else:
                st.info("No approval action required")

            st.divider()

            # ── file actions — download, view, delete (ALL documents) ─────────
            file_path = Path(str(doc.get("file_path", "")))

            download_col, view_col, delete_col = st.columns(3)

            with download_col:
                if file_path.exists():
                    with open(file_path, "rb") as f:
                        st.download_button(
                            "⬇ Download",
                            f,
                            file_name=doc["file_name"],
                            key=f"download_{doc['id']}"
                        )

            with view_col:
                if file_path.exists():
                    if st.button("👁 View", key=f"view_{doc['id']}"):
                        with open(file_path, "rb") as f:
                            st.session_state["view_document"] = f.read()
                            st.session_state["view_filename"] = doc["file_name"]
                            st.rerun()

            with delete_col:
                if st.button("🗑 Delete", key=f"delete_{doc['id']}"):
                    if file_path.exists():
                        file_path.unlink()
                    db.delete_document(doc["id"])
                    st.success("Document deleted")
                    st.rerun()

    # ── document viewer ───────────────────────────────────────────────────────
    if "view_document" in st.session_state:
        st.divider()
        fname = st.session_state["view_filename"]
        fdata = st.session_state["view_document"]
        st.subheader(f"👁 Viewing: {fname}")

        col_close, _ = st.columns([1, 5])
        with col_close:
            if st.button("✖ Close viewer", use_container_width=True):
                del st.session_state["view_document"]
                del st.session_state["view_filename"]
                st.rerun()

        ext = fname.lower().split(".")[-1]

        if ext == "pdf":
            try:
                import fitz
                pdf_doc = fitz.open(stream=fdata, filetype="pdf")
                st.caption(f"{pdf_doc.page_count} page(s)")
                for page_num in range(pdf_doc.page_count):
                    page = pdf_doc[page_num]
                    mat  = fitz.Matrix(2.0, 2.0)
                    pix  = page.get_pixmap(matrix=mat)
                    img_bytes = pix.tobytes("png")
                    st.image(img_bytes, caption=f"Page {page_num + 1}", use_container_width=True)
                pdf_doc.close()
            except Exception as e:
                st.error(f"Could not render PDF: {e}")

        elif ext in ("png", "jpg", "jpeg"):
            st.image(fdata, use_container_width=True)

        else:
            st.info("Preview not available for this file type. Use the Download button.")