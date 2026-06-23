import io
import pandas as pd

from reportlab.platypus import SimpleDocTemplate,Table,TableStyle,Paragraph,Spacer
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet


def filter_reports(documents,start_date=None,end_date=None,vendor=None,status=None,min_amount=0,max_amount=0):

    df=documents.copy()

    df["invoice_date"]=pd.to_datetime(
        df["invoice_date"],
        errors="coerce"
    )


    if start_date:

        df=df[
            df["invoice_date"].dt.date>=start_date
        ]


    if end_date:

        df=df[
            df["invoice_date"].dt.date<=end_date
        ]


    if vendor and vendor!="All":

        df=df[
            df["vendor_name"]
            .str.contains(
                vendor,
                case=False,
                na=False
            )
        ]


    if status and status!="All":

        df=df[
            df["status"]
            .fillna("")
            .str.lower()
            ==
            status.lower()
        ]


    if min_amount>0:

        df=df[
            df["amount"]>=min_amount
        ]


    if max_amount>0:

        df=df[
            df["amount"]<=max_amount
        ]


    return df



def spend_summary(df):
    """
    Only count documents that are pending or approved.
    Duplicates and rejected documents are excluded from all financial figures
    since they represent invalid or cancelled transactions.
    """
    # Filter to valid documents only
    valid = df[df["status"].str.lower().isin(["pending", "approved"])] if not df.empty else df

    if valid.empty:
        return {
            "Total Spend": 0,
            "Average Invoice": 0,
            "Documents": 0,
            "VAT": 0,
            "Excluded Duplicates": len(df[df["status"].str.lower() == "duplicate"]) if not df.empty else 0,
            "Excluded Rejected": len(df[df["status"].str.lower() == "rejected"]) if not df.empty else 0,
        }

    return {
        "Total Spend": float(valid["amount"].fillna(0).sum()),
        "Average Invoice": float(valid["amount"].fillna(0).mean()),
        "Documents": len(valid),
        "VAT": float(valid["vat_amount"].fillna(0).sum()),
        "Excluded Duplicates": len(df[df["status"].str.lower() == "duplicate"]),
        "Excluded Rejected": len(df[df["status"].str.lower() == "rejected"]),
    }



def vendor_analysis(df):
    """Only analyses valid (pending/approved) documents."""
    if df.empty:
        return pd.DataFrame()

    valid = df[df["status"].str.lower().isin(["pending", "approved"])]
    if valid.empty:
        return pd.DataFrame()

    return (
        valid.groupby("vendor_name")
        .agg(
            Total_Spend=("amount", "sum"),
            Documents=("id", "count"),
            VAT=("vat_amount", "sum")
        )
        .reset_index()
        .sort_values("Total_Spend", ascending=False)
    )



def approval_analysis(df):
    """Status breakdown excludes duplicates — they are not part of the workflow."""
    if df.empty:
        return pd.DataFrame()

    workflow_docs = df[df["status"].str.lower() != "duplicate"]
    if workflow_docs.empty:
        return pd.DataFrame()

    result = workflow_docs["status"].value_counts().reset_index()
    result.columns = ["Status", "Count"]
    return result



def ai_insights(df):
    """
    Generate AI-driven insights on the FILTERED dataset.
    Financial figures only count pending/approved documents.
    Duplicates and rejected are reported separately.
    """
    if df.empty:
        return ["No documents match the current filters."]

    insights = []

    # Valid documents only for financial analysis
    valid = df[df["status"].str.lower().isin(["pending", "approved"])]
    amounts = valid["amount"].fillna(0)
    total = amounts.sum()
    vat = valid["vat_amount"].fillna(0).sum()
    count = len(valid)
    avg = amounts.mean() if count > 0 else 0

    # --- Spending overview ---
    insights.append(
        f"Total spending in this report: R {total:,.2f} across {count} document(s)."
    )

    # VAT rate should be calculated against subtotal, not total
    # (VAT is applied to subtotal, so vat/total would always be less than the actual rate)
    subtotal_sum = valid["subtotal"].fillna(0).sum() if "subtotal" in valid.columns else 0
    if subtotal_sum > 0:
        actual_vat_rate = (vat / subtotal_sum * 100)
        insights.append(
            f"Total VAT recorded: R {vat:,.2f} "
            f"({actual_vat_rate:.1f}% of subtotal)."
        )
    elif total > 0:
        insights.append(f"Total VAT recorded: R {vat:,.2f}.")

    # --- Vendor concentration ---
    vendor = valid.groupby("vendor_name")["amount"].sum().sort_values(ascending=False)

    if len(vendor) > 0:
        top_vendor = vendor.index[0]
        top_vendor_pct = (vendor.iloc[0] / total * 100) if total > 0 else 0
        insights.append(
            f"Highest spending vendor: {top_vendor} "
            f"(R {vendor.iloc[0]:,.2f}, {top_vendor_pct:.1f}% of total spend)."
        )

    if len(vendor) == 1:
        insights.append(
            "⚠ Vendor concentration risk: all spend is with a single vendor."
        )
    elif len(vendor) >= 2 and total > 0:
        top2_pct = (vendor.iloc[:2].sum() / total * 100)
        if top2_pct > 80:
            insights.append(
                f"⚠ Vendor concentration risk: top 2 vendors account for "
                f"{top2_pct:.1f}% of total spend."
            )

    # --- Anomaly detection: unusually large invoices ---
    if count >= 3:
        std = amounts.std()
        threshold = avg + (2 * std)
        anomalies = valid[amounts > threshold]
        if not anomalies.empty:
            for _, row in anomalies.iterrows():
                insights.append(
                    f"⚠ Anomaly: {row['vendor_name']} invoice #{row['invoice_number']} "
                    f"(R {row['amount']:,.2f}) is significantly above the average "
                    f"(R {avg:,.2f}) for this report."
                )
        else:
            insights.append(
                f"No unusual invoice amounts detected "
                f"(average: R {avg:,.2f})."
            )

    # --- Approval status breakdown ---
    pending = len(df[df["status"].str.lower() == "pending"])
    approved = len(df[df["status"].str.lower() == "approved"])
    rejected = len(df[df["status"].str.lower() == "rejected"])
    duplicates = len(df[df["status"].str.lower() == "duplicate"])

    if pending > 0:
        insights.append(
            f"{pending} document(s) are still awaiting approval — "
            f"R {df[df['status'].str.lower()=='pending']['amount'].fillna(0).sum():,.2f} on hold."
        )
    if rejected > 0:
        insights.append(
            f"{rejected} document(s) were rejected — "
            f"review these with the relevant approver."
        )
    if duplicates > 0:
        insights.append(
            f"{duplicates} duplicate document(s) detected — "
            f"these did not enter the approval workflow."
        )
    if pending == 0 and rejected == 0:
        insights.append(
            "All documents in this report have been fully processed."
        )

    # --- VAT efficiency ---
    if subtotal_sum > 0:
        effective_vat_rate = (vat / subtotal_sum * 100)
        if effective_vat_rate < 13:
            insights.append(
                f"⚠ Effective VAT rate is {effective_vat_rate:.1f}% of subtotal — "
                f"lower than the standard 15%. Some invoices may be missing VAT."
            )
        elif effective_vat_rate > 17:
            insights.append(
                f"⚠ Effective VAT rate is {effective_vat_rate:.1f}% of subtotal — "
                f"higher than the standard 15%. Check for data entry errors."
            )

    return insights



def export_excel(df,summary,vendor_data,status_data,insights):

    output=io.BytesIO()


    with pd.ExcelWriter(
        output,
        engine="openpyxl"
    ) as writer:


        pd.DataFrame({

            "Metric":[
                "Documents",
                "Total Spend",
                "VAT",
                "Average Invoice"
            ],

            "Value":[
                summary["Documents"],
                summary["Total Spend"],
                summary["VAT"],
                summary["Average Invoice"]
            ]

        }).to_excel(
            writer,
            sheet_name="Overview",
            index=False
        )


        vendor_data.to_excel(
            writer,
            sheet_name="Vendor Analysis",
            index=False
        )


        status_data.to_excel(
            writer,
            sheet_name="Approval Status",
            index=False
        )


        pd.DataFrame({

            "AI Insights":insights

        }).to_excel(
            writer,
            sheet_name="AI Analysis",
            index=False
        )


        invoice=df.drop(
            columns=[
                "file_hash",
                "file_path"
            ],
            errors="ignore"
        )


        invoice.to_excel(
            writer,
            sheet_name="Invoice Register",
            index=False
        )


        workbook=writer.book


        for sheet in workbook:

            sheet.freeze_panes="A2"


            for column in sheet.columns:

                length=max(
                    len(str(cell.value))
                    if cell.value else 0
                    for cell in column
                )

                sheet.column_dimensions[
                    column[0].column_letter
                ].width=min(
                    length+3,
                    35
                )


    output.seek(0)

    return output.getvalue()



def _safe_str(val, max_len=25):
    """Convert value to clean string, stripping NaN/NaT/None."""
    if val is None:
        return ""
    s = str(val).strip()
    if s.lower() in ("nan", "none", "nat", ""):
        return ""
    # Truncate ISO datetimes to date only
    if "T" in s and len(s) > 10:
        s = s[:10]
    return s[:max_len] if max_len else s


def export_pdf(df, summary, vendor_data, status_data, insights, company_id=None):
    """
    Portrait A4 PDF report.
    Only pending/approved documents appear in financial tables.
    Approval breakdown shows who acted, when, and any comment.
    """
    import sqlite3
    from datetime import datetime
    from database import DB_PATH

    output = io.BytesIO()
    pdf = SimpleDocTemplate(
        output, pagesize=A4,
        leftMargin=30, rightMargin=30, topMargin=30, bottomMargin=30,
    )
    styles = getSampleStyleSheet()
    small = styles["Normal"].clone("small")
    small.fontSize = 8
    elements = []

    # ── Title ────────────────────────────────────────────────────────────────
    elements.append(Paragraph("DocuManage — Report & AI Insights", styles["Title"]))
    elements.append(Spacer(1, 6))
    elements.append(Paragraph(
        f"Generated: {datetime.now().strftime('%d %B %Y %H:%M')}",
        styles["Normal"]
    ))
    elements.append(Spacer(1, 14))

    # Valid documents only for all financial sections
    valid = df[df["status"].str.lower().isin(["pending", "approved"])].copy() \
        if not df.empty else df.copy()

    excl_dup = len(df[df["status"].str.lower() == "duplicate"]) if not df.empty else 0
    excl_rej = len(df[df["status"].str.lower() == "rejected"]) if not df.empty else 0

    # ── Spend Summary ─────────────────────────────────────────────────────────
    elements.append(Paragraph("Spend Summary", styles["Heading2"]))
    elements.append(Spacer(1, 5))
    elements.append(Paragraph(
        "Financial totals include only pending and approved documents.",
        small
    ))
    elements.append(Spacer(1, 5))

    summary_rows = [
        ["Valid Documents", "Total Spend", "Total VAT", "Average Invoice"],
        [
            str(summary["Documents"]),
            f"R {summary['Total Spend']:,.2f}",
            f"R {summary['VAT']:,.2f}",
            f"R {summary['Average Invoice']:,.2f}",
        ]
    ]
    if excl_dup > 0 or excl_rej > 0:
        summary_rows.append([
            f"Excluded: {excl_dup} duplicate(s), {excl_rej} rejected",
            "", "", ""
        ])

    t = Table(summary_rows, colWidths=[118, 118, 118, 118])
    t.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, 0), "#1F2937"),
        ("TEXTCOLOR",     (0, 0), (-1, 0), "#FFFFFF"),
        ("FONTNAME",      (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE",      (0, 0), (-1, -1), 9),
        ("ALIGN",         (0, 0), (-1, -1), "CENTER"),
        ("GRID",          (0, 0), (-1, -1), 0.5, "#CCCCCC"),
        ("TOPPADDING",    (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("SPAN",          (0, 2), (-1, 2)),
        ("FONTSIZE",      (0, 2), (-1, 2), 7),
        ("TEXTCOLOR",     (0, 2), (-1, 2), "#6B7280"),
    ]))
    elements.append(t)
    elements.append(Spacer(1, 14))

    # ── Vendor Analysis ───────────────────────────────────────────────────────
    elements.append(Paragraph("Vendor Analysis", styles["Heading2"]))
    elements.append(Spacer(1, 5))

    if not vendor_data.empty:
        vrows = [["Vendor", "Total Spend (R)", "Documents", "VAT (R)"]]
        for _, row in vendor_data.iterrows():
            vrows.append([
                _safe_str(row.get("vendor_name", ""), 30),
                f"{float(row.get('Total_Spend', 0)):,.2f}",
                str(int(row.get("Documents", 0))),
                f"{float(row.get('VAT', 0)):,.2f}",
            ])
        vt = Table(vrows, colWidths=[190, 100, 70, 100])
        vt.setStyle(TableStyle([
            ("BACKGROUND",    (0, 0), (-1, 0), "#374151"),
            ("TEXTCOLOR",     (0, 0), (-1, 0), "#FFFFFF"),
            ("FONTNAME",      (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE",      (0, 0), (-1, -1), 9),
            ("ALIGN",         (1, 0), (-1, -1), "RIGHT"),
            ("GRID",          (0, 0), (-1, -1), 0.5, "#CCCCCC"),
            ("ROWBACKGROUNDS",(0, 1), (-1, -1), ["#FFFFFF", "#F9FAFB"]),
            ("TOPPADDING",    (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        elements.append(vt)
    else:
        elements.append(Paragraph("No vendor data for the current filters.", small))
    elements.append(Spacer(1, 14))

    # ── Approval Status Breakdown — with who, when, and comment ──────────────
    elements.append(Paragraph("Approval Status Breakdown", styles["Heading2"]))
    elements.append(Spacer(1, 5))

    # Fetch approval details from database for each document in this report
    approval_rows = [["Document", "Step", "Role", "Decision", "By", "Date", "Comment"]]
    approval_found = False

    if not df.empty:
        try:
            conn = sqlite3.connect(DB_PATH)
            conn.row_factory = sqlite3.Row
            for _, doc in df.iterrows():
                doc_id = int(doc["id"])
                rows = conn.execute(
                    """
                    SELECT a.step, a.role_required, a.status,
                           u.full_name as approver_name,
                           a.actioned_at, a.comments
                    FROM approvals a
                    LEFT JOIN users u ON a.approver_id = u.id
                    WHERE a.document_id = ?
                    ORDER BY a.step
                    """,
                    (doc_id,)
                ).fetchall()
                for row in rows:
                    if row["status"] and row["status"].lower() != "pending":
                        approval_found = True
                        fname = _safe_str(doc["file_name"], 20)
                        role_label = {
                            "reviewer": "Reviewer",
                            "manager": "Manager",
                            "finance/admin": "Finance/Admin"
                        }.get(str(row["role_required"]).lower(), row["role_required"])
                        approval_rows.append([
                            fname,
                            str(row["step"]),
                            role_label,
                            str(row["status"]).upper(),
                            _safe_str(row["approver_name"], 20),
                            _safe_str(row["actioned_at"])[:10],
                            _safe_str(row["comments"], 30),
                        ])
            conn.close()
        except Exception:
            pass

    if approval_found:
        at = Table(approval_rows, colWidths=[70, 28, 70, 55, 70, 55, 100])
        at.setStyle(TableStyle([
            ("BACKGROUND",    (0, 0), (-1, 0), "#374151"),
            ("TEXTCOLOR",     (0, 0), (-1, 0), "#FFFFFF"),
            ("FONTNAME",      (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE",      (0, 0), (-1, -1), 7),
            ("GRID",          (0, 0), (-1, -1), 0.25, "#CCCCCC"),
            ("ROWBACKGROUNDS",(0, 1), (-1, -1), ["#FFFFFF", "#F9FAFB"]),
            ("TOPPADDING",    (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ]))
        elements.append(at)
    else:
        elements.append(Paragraph("No approval actions recorded yet.", small))
    elements.append(Spacer(1, 14))

    # ── Tax / VAT Report — valid docs only ───────────────────────────────────
    elements.append(Paragraph("Tax / VAT Report", styles["Heading2"]))
    elements.append(Spacer(1, 5))

    vat_total      = float(valid["vat_amount"].fillna(0).sum())
    subtotal_total = float(valid["subtotal"].fillna(0).sum()) if "subtotal" in valid.columns else 0.0
    elements.append(Paragraph(
        f"Total VAT (pending/approved only): R {vat_total:,.2f}   "
        f"|   Subtotal: R {subtotal_total:,.2f}",
        styles["Normal"]
    ))
    elements.append(Spacer(1, 14))

    # ── AI Insights ───────────────────────────────────────────────────────────
    elements.append(Paragraph("AI-Driven Insights", styles["Heading2"]))
    elements.append(Spacer(1, 5))
    for insight in insights:
        clean = insight.replace("⚠ ", "[!] ").replace("⚠", "[!]")
        elements.append(Paragraph(f"• {clean}", styles["Normal"]))
        elements.append(Spacer(1, 3))
    elements.append(Spacer(1, 14))

    # ── Invoice Register — valid docs only ────────────────────────────────────
    elements.append(Paragraph("Invoice Register (pending & approved only)", styles["Heading2"]))
    elements.append(Spacer(1, 5))

    if valid.empty:
        elements.append(Paragraph("No valid documents to display.", small))
    else:
        reg = valid[[
            "file_name", "document_type", "vendor_name",
            "invoice_number", "invoice_date",
            "subtotal", "vat_amount", "amount", "status"
        ]].copy()

        reg_rows = [["File", "Type", "Vendor", "Inv #", "Date", "Subtotal", "VAT", "Total", "Status"]]
        for _, row in reg.iterrows():
            reg_rows.append([
                _safe_str(row["file_name"], 18),
                _safe_str(row["document_type"], 10).replace("_"," ").title(),
                _safe_str(row["vendor_name"], 18),
                _safe_str(row["invoice_number"], 12),
                _safe_str(row["invoice_date"])[:10],
                f"R{float(row['subtotal'] or 0):,.2f}",
                f"R{float(row['vat_amount'] or 0):,.2f}",
                f"R{float(row['amount'] or 0):,.2f}",
                _safe_str(row["status"]).title(),
            ])

        rt = Table(reg_rows,
                   colWidths=[60, 42, 70, 45, 45, 46, 40, 46, 38],
                   repeatRows=1)
        rt.setStyle(TableStyle([
            ("BACKGROUND",    (0, 0), (-1, 0), "#1F2937"),
            ("TEXTCOLOR",     (0, 0), (-1, 0), "#FFFFFF"),
            ("FONTNAME",      (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE",      (0, 0), (-1, -1), 7),
            ("ALIGN",         (5, 0), (-1, -1), "RIGHT"),
            ("GRID",          (0, 0), (-1, -1), 0.25, "#CCCCCC"),
            ("ROWBACKGROUNDS",(0, 1), (-1, -1), ["#FFFFFF", "#F9FAFB"]),
            ("TOPPADDING",    (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ]))
        elements.append(rt)

    pdf.build(elements)
    output.seek(0)
    return output.getvalue()
