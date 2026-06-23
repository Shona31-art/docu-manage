"""
reports_page.py
Dedicated reports and AI insights page.
Filters apply to all sections including AI insights.
"""

import pandas as pd
import streamlit as st
import database as db
import reports


def reports_page():

    st.header("📊 Reports & AI Insights")

    company_id = st.session_state.user["company_id"]
    all_docs = db.get_company_documents(company_id)

    if all_docs.empty:
        st.info("No documents to report on yet. Upload some documents first.")
        return

    # ---------- FILTERS ----------

    st.subheader("Filters")
    st.caption("All sections below — including AI insights — reflect the filtered data.")

    col1, col2, col3 = st.columns(3)

    with col1:
        start_date = st.date_input("From date", value=None)
        end_date = st.date_input("To date", value=None)

    with col2:
        vendors = ["All"] + sorted(
            all_docs["vendor_name"].dropna().unique().tolist()
        )
        vendor = st.selectbox("Vendor name", vendors)
        status = st.selectbox(
            "Approval status",
            ["All", "pending", "approved", "rejected", "duplicate"]
        )

    with col3:
        min_amount = st.number_input("Min amount (R)", min_value=0.0, value=0.0, step=100.0)
        max_amount = st.number_input("Max amount (R)", min_value=0.0, value=0.0, step=100.0)

    # Apply filters — insights will use this same filtered dataset
    filtered = reports.filter_reports(
        all_docs,
        start_date=start_date if start_date else None,
        end_date=end_date if end_date else None,
        vendor=vendor,
        status=status,
        min_amount=min_amount,
        max_amount=max_amount,
    )

    st.divider()

    if filtered.empty:
        st.warning("No documents match the current filters.")
        return

    st.caption(f"Showing {len(filtered)} of {len(all_docs)} document(s).")

    # ---------- SPEND SUMMARY ----------

    st.subheader("💰 Spend summary")
    st.caption("Financial totals exclude duplicate and rejected documents.")

    summary = reports.spend_summary(filtered)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Valid documents", summary["Documents"])
    c2.metric("Total spend", f"R {summary['Total Spend']:,.2f}")
    c3.metric("Total VAT", f"R {summary['VAT']:,.2f}")
    c4.metric("Average invoice", f"R {summary['Average Invoice']:,.2f}")

    excl_dup = summary.get("Excluded Duplicates", 0)
    excl_rej = summary.get("Excluded Rejected", 0)
    if excl_dup > 0 or excl_rej > 0:
        st.info(
            f"ℹ️ Excluded from totals: "
            f"{excl_dup} duplicate(s) and {excl_rej} rejected document(s). "
            f"These do not represent valid transactions."
        )

    st.divider()

    # ---------- VENDOR ANALYSIS ----------

    st.subheader("🏢 Vendor analysis")

    vendor_data = reports.vendor_analysis(filtered)
    status_data = reports.approval_analysis(filtered)

    if vendor_data.empty:
        st.info("No vendor data for the current filters.")
    else:
        st.dataframe(
            vendor_data,
            use_container_width=True,
            hide_index=True
        )

    st.divider()

    # ---------- APPROVAL STATUS ----------

    st.subheader("🔄 Approval status breakdown")
    st.caption("Shows each document's approval chain — who acted, when, and what is still waiting.")

    import sqlite3
    from database import DB_PATH

    STEP_LABELS = {
        "reviewer":     "Reviewer",
        "manager":      "Manager",
        "finance/admin":"Finance/Admin",
    }

    # Build a detailed table: one row per approval step per document
    detail_rows = []

    for _, doc in filtered.iterrows():
        if doc["status"].lower() == "duplicate":
            continue  # duplicates never entered workflow

        try:
            conn = sqlite3.connect(DB_PATH)
            conn.row_factory = sqlite3.Row
            steps = conn.execute(
                """
                SELECT a.step, a.role_required, a.status,
                       u.full_name as approver_name,
                       a.actioned_at, a.comments
                FROM approvals a
                LEFT JOIN users u ON a.approver_id = u.id
                WHERE a.document_id = ?
                ORDER BY a.step
                """,
                (int(doc["id"]),)
            ).fetchall()
            conn.close()
        except Exception:
            continue

        for step in steps:
            role    = str(step["role_required"]).lower()
            status  = str(step["status"]).lower()
            name    = step["approver_name"] or ""
            acted   = str(step["actioned_at"] or "")[:10]
            comment = str(step["comments"] or "").strip()

            # Clean nan values
            if name.lower()    in ("nan","none",""):  name    = "—"
            if acted.lower()   in ("nan","none",""):  acted   = "—"
            if comment.lower() in ("nan","none",""):  comment = "—"

            if status == "pending":
                decision  = "⏳ Pending"
                who       = f"Waiting for {STEP_LABELS.get(role, role)}"
                date_str  = "—"
                comment   = "—"
            elif status == "approved":
                decision  = "✅ Approved"
                who       = name
                date_str  = acted
            else:
                decision  = "❌ Rejected"
                who       = name
                date_str  = acted

            detail_rows.append({
                "Document":    str(doc["file_name"])[:22],
                "Inv #":       str(doc["invoice_number"] or "—")[:12],
                "Step":        f"Step {step['step']}",
                "Role":        STEP_LABELS.get(role, role),
                "Decision":    decision,
                "By / Waiting":who,
                "Date":        date_str,
                "Comment":     comment,
            })

    if detail_rows:
        approval_detail_df = pd.DataFrame(detail_rows)
        st.dataframe(
            approval_detail_df,
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info("No approval activity yet for the current filters.")

    st.divider()

    # ---------- TAX / VAT REPORT ----------

    st.subheader("🧾 Tax / VAT report")
    st.caption("Only pending and approved documents are included.")

    valid_docs = filtered[filtered["status"].str.lower().isin(["pending", "approved"])]

    vat_df = valid_docs[[
        "vendor_name", "invoice_number", "invoice_date",
        "subtotal", "vat_amount", "amount", "status"
    ]].copy() if not valid_docs.empty else pd.DataFrame()

    if not vat_df.empty:
        vat_df = vat_df.rename(columns={
            "vendor_name": "Vendor",
            "invoice_number": "Invoice #",
            "invoice_date": "Date",
            "subtotal": "Subtotal (R)",
            "vat_amount": "VAT (R)",
            "amount": "Total (R)",
            "status": "Status",
        })
        st.dataframe(vat_df, use_container_width=True, hide_index=True)
        vat_total = valid_docs["vat_amount"].fillna(0).sum()
        subtotal_total = valid_docs["subtotal"].fillna(0).sum() if "subtotal" in valid_docs.columns else 0
        st.markdown(f"**VAT total: R {vat_total:,.2f}** on a subtotal of R {subtotal_total:,.2f}")
    else:
        st.info("No valid documents to report on.")

    st.divider()

    # ---------- EXCLUDED DOCUMENTS ----------
    excluded = filtered[filtered["status"].str.lower().isin(["duplicate", "rejected"])]

    with st.expander(
        f"🚫 Excluded documents ({len(excluded)}) — duplicates & rejected",
        expanded=False
    ):
        if excluded.empty:
            st.info("No excluded documents for the current filters.")
        else:
            st.caption(
                "These documents were excluded from all spend totals, VAT figures, "
                "and vendor analysis above. Shown here for full transparency."
            )
            for _, row in excluded.iterrows():
                status = str(row.get("status", "")).lower()
                icon   = "⚠️" if status == "duplicate" else "❌"
                reason = (
                    "Duplicate — same invoice number or vendor/amount already exists."
                    if status == "duplicate"
                    else "Rejected during approval workflow — did not pass all 3 steps."
                )
                st.markdown(
                    f"{icon} **{row['file_name']}** | "
                    f"{row['vendor_name']} | #{row['invoice_number']} | "
                    f"R {float(row['amount'] or 0):,.2f}  \n"
                    f"<small style='color:grey'>{reason}</small>",
                    unsafe_allow_html=True,
                )

    st.divider()

    # ---------- AI INSIGHTS ----------
    # Insights run on the FILTERED dataset, not the full document set.
    # This is the key requirement from the brief: insights ON the reports.

    st.subheader("🤖 AI-driven insights")
    st.caption(
        "These insights are generated from the documents currently visible "
        "above. Adjust the filters to analyse different slices of your data."
    )

    insights = reports.ai_insights(filtered)

    for insight in insights:
        if insight.startswith("⚠"):
            st.warning(insight)
        else:
            st.info(insight)

    st.divider()

    # ---------- EXPORT ----------

    st.subheader("📥 Export")

    col_pdf, col_excel = st.columns(2)

    with col_pdf:
        pdf_bytes = reports.export_pdf(
            filtered, summary, vendor_data, status_data, insights,
            company_id=company_id
        )
        st.download_button(
            "📄 Download PDF report",
            pdf_bytes,
            file_name="docu_manage_report.pdf",
            mime="application/pdf",
            use_container_width=True,
        )

    with col_excel:
        excel_bytes = reports.export_excel(
            filtered, summary, vendor_data, status_data, insights
        )
        st.download_button(
            "📊 Download Excel report",
            excel_bytes,
            file_name="docu_manage_report.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )
