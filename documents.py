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
    "reviewer": "Reviewer",
    "manager": "Manager",
    "finance/admin": "Finance/Admin"
}

STATUS_COLOR = {
    "approved": "#EAF3DE",
    "pending": "#FAEEDA",
    "rejected": "#FCEBEB",
    "duplicate": "#FEF3C7",
}

STATUS_ICON = {
    "approved": "✅",
    "pending": "⏳",
    "rejected": "❌",
    "duplicate": "⚠️",
}


def _safe(val):
    if val is None:
        return ""

    s = str(val).strip()

    return "" if s.lower() in ("nan", "none", "nat", "") else s


def _step_display(status):

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


    total = len(docs)
    pending = len(docs[docs["status"] == "pending"])
    approved = len(docs[docs["status"] == "approved"])
    rejected = len(docs[docs["status"] == "rejected"])
    duplicate = len(docs[docs["status"] == "duplicate"])


    c1,c2,c3,c4,c5 = st.columns(5)

    c1.metric("Total", total)
    c2.metric("⏳ Pending", pending)
    c3.metric("✅ Approved", approved)
    c4.metric("❌ Rejected", rejected)
    c5.metric("⚠️ Duplicate", duplicate)

    st.divider()

    user_role = st.session_state.user["role"].lower()

    for idx, (_, doc) in enumerate(docs.iterrows(),1):

        status = str(doc.get("status","pending"))

        bg = STATUS_COLOR.get(status,"#F9FAFB")

        icon = STATUS_ICON.get(status,"📄")

        doc_type = str(
            doc.get("document_type","invoice")
        ).replace("_"," ").title()

        st.markdown(
            f"""
            <div style="
            background:{bg};
            padding:4px 12px;
            border:1px solid #D1D5DB;
            border-bottom:none;
            border-radius:4px 4px 0 0;">
            <small>
            {icon} {idx}/{total} —
            {doc["file_name"]}
            <b style="float:right">
            {status.upper()}
            </b>
            </small>
            </div>
            """,
            unsafe_allow_html=True
        )

        with st.container(border=True):

            if doc["is_duplicate"]:
                st.caption(
                    "⚠️ Duplicate — excluded from approval workflow."
                )

            col1,col2 = st.columns(2)

            with col1:

                st.caption(
                    f"**Vendor:** {doc['vendor_name'] or '—'}"
                )

                st.caption(
                    f"**Invoice #:** {doc['invoice_number'] or '—'}"
                )

                st.caption(
                    f"**Date:** {doc['invoice_date'] or '—'} · {doc_type}"
                )

            with col2:

                st.caption(
                    f"**Subtotal:** R {float(doc['subtotal'] or 0):,.2f}"
                )

                st.caption(
                    f"**VAT:** R {float(doc['vat_amount'] or 0):,.2f}"
                )

                st.caption(
                    f"**Total:** R {float(doc['amount'] or 0):,.2f}"
                )

            st.divider()


            st.markdown("**🔄 Approval Workflow**")


            approvals = db.get_document_approvals(doc["id"])

            approved_count = 0

            step_cols = st.columns(3)


            for i,step in enumerate(STEP_ORDER):

                row = approvals[
                    approvals["role_required"].str.lower() == step
                ] if not approvals.empty else None


                step_status = "waiting"


                if row is not None and not row.empty:

                    step_status = row.iloc[0]["status"].lower()


                with step_cols[i]:

                    st.markdown(
                        f"{_step_display(step_status)} "
                        f"**{STEP_LABEL[step]}**"
                    )


                if step_status == "approved":
                    approved_count += 1

            st.caption(
                f"Approval Progress: {approved_count}/3"
            )


            st.divider()


            st.markdown("**📜 Approval History**")


            if not approvals.empty:

                acted = approvals[
                    approvals["status"] != "pending"
                ]

                for _,row in acted.iterrows():

                    st.write(
                        f"Step {int(row['step'])} — "
                        f"{STEP_LABEL[row['role_required']]}: "
                        f"**{row['status'].upper()}**"
                    )

            else:

                st.info("No approval activity yet")

            st.divider()

            st.markdown("**Approval Action**")

            file_path = Path(
                str(doc.get("file_path",""))
            )

            download_col,view_col,delete_col = st.columns(3)

            with download_col:

                if file_path.exists():

                    with open(file_path,"rb") as f:

                        st.download_button(
                            "⬇ Download",
                            f,
                            file_name=doc["file_name"],
                            key=f"download_{doc['id']}"
                        )

            with view_col:
                if file_path.exists():
                    if st.button("👁 View", key=f"view_{doc['id']}"):
                        with open(file_path,"rb") as f:
                            st.session_state["view_document"]=f.read()

                            st.session_state["view_filename"]=doc["file_name"]
                            st.session_state["view_doc_id"]=doc["id"]
                            st.rerun()

            with delete_col:

                if st.button(
                    "🗑 Delete",
                    key=f"delete_{doc['id']}"
                ):

                    if file_path.exists():

                        file_path.unlink()

                    db.delete_document(doc["id"])

                    st.rerun()

    # VIEWER

    if st.session_state.get("view_doc_id")==doc["id"]:

        st.divider()

        st.subheader(f"👁 Viewing: {doc['file_name']}")

    if st.button("✖ Close Viewer",key=f"close_{doc['id']}"):
        del st.session_state["view_document"]
        del st.session_state["view_filename"]
        del st.session_state["view_doc_id"]
        st.rerun()

    data=st.session_state["view_document"]

    ext=doc["file_name"].lower().split(".")[-1]

    if ext=="pdf":
        import fitz

        pdf=fitz.open(stream=data,filetype="pdf")

        for page in pdf:
            pix=page.get_pixmap(matrix=fitz.Matrix(2,2))
            st.image(
                pix.tobytes("png"),
                use_container_width=True
            )

        pdf.close()

    elif ext in ("png","jpg","jpeg"):
        st.image(
            data,
            use_container_width=True
        )