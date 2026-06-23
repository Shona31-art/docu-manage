import pytesseract
from PIL import Image
import fitz
import re
import os

# Windows: point pytesseract at the default Tesseract install location.
# If Tesseract is installed somewhere else, update this path.
TESSERACT_PATH = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

if os.path.exists(TESSERACT_PATH):
    pytesseract.pytesseract.tesseract_cmd = TESSERACT_PATH

try:
    pytesseract.get_tesseract_version()
    TESSERACT_AVAILABLE = True
except Exception:
    TESSERACT_AVAILABLE = False
    
def _parse_amount(raw: str) -> float:
    """Turn '12,450.00' or 'R12,450.00' into 12450.00"""
    cleaned = raw.replace(",", "").replace("R", "").strip()
    return float(cleaned)


def _find_labeled_amount(text: str, label_pattern: str):
    """
    Look for a specific label followed by a currency amount.
    Explicitly skips percentage values (e.g. VAT (6.25%) -> skips 6.25,
    finds the actual rand amount that follows).
    Handles amounts with thousand separators, e.g. R12,450.00
    """
    # Strip out percentage values first so they don't get matched as amounts
    clean_text = re.sub(r'\d+\.?\d*\s*%', '', text)
    pattern = label_pattern + r"[^\d]{0,20}(R?\s?\d{1,3}(?:,\d{3})*\.\d{2})"
    match = re.search(pattern, clean_text, re.I)
    if match:
        return _parse_amount(match.group(1))
    return None


def _find_date(text: str):
    """Match common date formats: '10 June 2026', '10/06/2026', '2026-06-10'"""
    patterns = [
        r"(\d{1,2}\s+\w+\s+\d{4})",        # 10 June 2026
        r"(\d{4}-\d{2}-\d{2})",            # 2026-06-10
        r"(\d{1,2}/\d{1,2}/\d{4})",        # 10/06/2026
    ]
    for p in patterns:
        match = re.search(r"(?:invoice date|date)[^\d]{0,10}" + p, text, re.I)
        if match:
            return match.group(1)
    return ""


def _detect_document_type(text: str) -> str:
    """Look for explicit 'credit note' wording; default to invoice otherwise."""
    if re.search(r"credit\s*note", text, re.I):
        return "credit_note"
    return "invoice"


def extract_invoice_data(file_path):
    text = ""

    if file_path.lower().endswith(".pdf"):
        pdf = fitz.open(file_path)
        for page in pdf:
            text += page.get_text()

    elif file_path.lower().endswith((".png", ".jpg", ".jpeg")):
        if TESSERACT_AVAILABLE:
            image = Image.open(file_path)
            text = pytesseract.image_to_string(image)
        else:
            # Tesseract not installed — return empty extraction so the user
            # can fill in the form fields manually. PDF uploads still work fully.
            text = ""

    data = {
        "vendor_name": "",
        "invoice_number": "",
        "invoice_date": "",
        "subtotal": 0,
        "vat_amount": 0,
        "amount": 0,
        "document_type": "invoice",
    }

    data["document_type"] = _detect_document_type(text)

    # Document number — look for labelled number fields first (most reliable)
    # This handles "Credit Note No: CN-1234", "Invoice #: INV-001" etc.
    labelled_num = re.search(
        r"(?:credit\s*note\s*(?:no\.?|number|#)?|invoice\s*(?:no\.?|number|#)?)"
        r"\s*[:#]?\s*([A-Z]{0,4}[-]?\d{2,}[-\w]*)",
        text, re.I
    )
    if labelled_num:
        data["invoice_number"] = labelled_num.group(1).upper().strip()
    else:
        # Fallback: look for prefixed document numbers (INV-, CN-, etc.)
        doc_num = re.search(
            r"\b((?:INV|CN|CR|CRN|CDN)[-]\d+[\w-]*)\b",
            text, re.I
        )
        if doc_num:
            data["invoice_number"] = doc_num.group(1).upper().strip()

    # Date
    data["invoice_date"] = _find_date(text)

    # Amounts — search by label first, then fall back to positional guess
    subtotal = _find_labeled_amount(text, r"sub[\s-]?total")

    # VAT: credit notes may label it as "VAT", "Tax", "VAT amount", "Tax amount"
    vat = (
        _find_labeled_amount(text, r"vat(?:\s*\(\d+%\))?(?:\s*amount)?")
        or _find_labeled_amount(text, r"tax(?:\s*amount)?")
    )

    # Total: avoid matching inside "Subtotal" using word boundary logic
    total = _find_labeled_amount(
        text, r"(?<!\w)total\s*(?:due|amount|payable|refund)?"
    )

    # If labeled search found nothing, fall back to last 3 currency amounts
    if subtotal is None and vat is None and total is None:
        all_amounts = re.findall(
            r"R?\s?\d{1,3}(?:,\d{3})*\.\d{2}", text
        )
        clean = []
        for a in all_amounts:
            try:
                clean.append(_parse_amount(a))
            except ValueError:
                pass
        if len(clean) >= 3:
            subtotal = clean[-3]
            vat = clean[-2]
            total = clean[-1]
        elif len(clean) == 2:
            vat = clean[-2]
            total = clean[-1]
        elif len(clean) == 1:
            total = clean[-1]

    if subtotal is not None:
        data["subtotal"] = subtotal
    if vat is not None:
        data["vat_amount"] = vat
    if total is not None:
        data["amount"] = total
    elif subtotal is not None and vat is not None:
        # If no explicit "total" label found, derive it
        data["amount"] = round(subtotal + vat, 2)

    # Vendor name — first meaningful line, skipping document type headers
    SKIP_WORDS = {
        "credit note", "tax invoice", "invoice", "receipt",
        "statement", "purchase order", "debit note", "remittance"
    }
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    for line in lines:
        if line.lower() not in SKIP_WORDS and len(line) > 2:
            data["vendor_name"] = line
            break

    return data

