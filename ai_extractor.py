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
    
    lines = text.splitlines()

    for i, line in enumerate(lines):

        if re.search(label_pattern, line, re.I):

            # check same line first
            amount = re.search(
                r"R?\s?(\d{1,3}(?:,\d{3})*\.\d{2})",
                line
            )

            if amount:
                return _parse_amount(amount.group(1))


            # check next 2 lines
            for next_line in lines[i+1:i+3]:

                amount = re.search(
                    r"R?\s?(\d{1,3}(?:,\d{3})*\.\d{2})",
                    next_line
                )

                if amount:
                    return _parse_amount(amount.group(1))

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
    # Document number

    fallback_num = None

        # Document number extraction

        # ==============================
    # Invoice / Credit Note Number
    # ==============================

    data["invoice_number"] = ""


    labelled_num = re.search(
        r"(?:invoice|credit\s*note|document)"
        r"\s*(?:no\.?|number|#)"
        r"\s*[:\-]?\s*([A-Z0-9][A-Z0-9\-_\/]+)",
        text,
        re.IGNORECASE
    )


    if labelled_num:

        value = labelled_num.group(1).upper().strip()


        blocked = [
            "CREDIT",
            "NOTE",
            "INVOICE",
            "TAX"
        ]


        if value not in blocked:
            data["invoice_number"] = value



    # fallback for formats without labels
    if data["invoice_number"] == "":

        fallback_num = re.search(
            r"\b[A-Z]{2,5}[-\/]?\d{2,}\b",
            text,
            re.IGNORECASE
        )


        if fallback_num:

            value = fallback_num.group(0).upper().strip()

            if value not in [
                "CREDIT",
                "INVOICE"
            ]:
                data["invoice_number"] = value

    # Date
    data["invoice_date"] = _find_date(text)

   # Amounts — support multiple invoice layouts and wording variations

    subtotal = (
    _find_labeled_amount(text, r"sub[\s-]?total")
    or _find_labeled_amount(text, r"net\s+amount")
    or _find_labeled_amount(text, r"amount\s+before\s+tax")
    or _find_labeled_amount(text, r"total\s+excl(?:usive)?\s*vat")
    or _find_labeled_amount(text, r"subtotal\s+excl(?:usive)?\s*vat")
    or _find_labeled_amount(text, r"goods\s+amount")
    or _find_labeled_amount(text, r"goods\s+total")
    or _find_labeled_amount(text, r"line\s+total")
    or _find_labeled_amount(text, r"net\s+total")
    )
    
    total = (
    _find_labeled_amount(text, r"(?<!\w)(?:grand\s*)?total(?!\s*(?:vat|tax))")
    or _find_labeled_amount(text, r"invoice\s+total")
    or _find_labeled_amount(text, r"total\s+incl(?:usive)?\s*vat")
    or _find_labeled_amount(text, r"total\s+including\s*vat")
    or _find_labeled_amount(text, r"total\s+amount")
    or _find_labeled_amount(text, r"total\s+due")
    or _find_labeled_amount(text, r"amount\s+due")
    or _find_labeled_amount(text, r"balance\s+due")
    or _find_labeled_amount(text, r"outstanding\s+balance")
    or _find_labeled_amount(text, r"remaining\s+balance")
    or _find_labeled_amount(text, r"balance\s+payable")
    or _find_labeled_amount(text, r"balance\s+amount")
    or _find_labeled_amount(text, r"amount\s+outstanding")
    or _find_labeled_amount(text, r"payable\s+amount")
    or _find_labeled_amount(text, r"total\s+payable")
    or _find_labeled_amount(text, r"final\s+amount")
    )

    vat = (

    _find_labeled_amount(text, r"value\s+added\s+tax")
    or _find_labeled_amount(text, r"tax(?:\s*amount)?")
    or _find_labeled_amount(text, r"vat\s+amount")
    or _find_labeled_amount(text, r"vat\s+total")
    or _find_labeled_amount(text, r"gst(?:\s*amount)?")
    or _find_labeled_amount(text, r"sales\s+tax")
    or _find_labeled_amount(text, r"(value\s+added\s+tax|vat)")
    or _find_labeled_amount(text, r"value\s+added\s+tax\s*\(\s*\d+%\s*\)")
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


    # Fix VAT using subtotal and total calculation
    if subtotal is not None and total is not None:

        calculated_vat = round(total - subtotal, 2)

    # Always trust calculation if VAT equals subtotal or is suspicious
    if vat is None or vat >= subtotal:

        vat = calculated_vat

    
        # ==============================
    # Vendor name extraction
    # ==============================

    lines = [
        line.strip()
        for line in text.splitlines()
        if line.strip()
    ]


    SKIP_WORDS = [
    "invoice",
    "tax invoice",
    "vat invoice",
    "credit",
    "credit note",
    "receipt",
    "statement",
    "purchase order",
    "po.",
    "po",
    "date",
    "number",
    "no",
    "vat",
    "total",
    "amount",
    "address",
    "postal code",
    "customer",
    "ship to",
    "balance",

    # table headings
    "vendor",
    "item",
    "description",
    "quantity",
    "qty",
    "unit",
    "unit price",
    "price",
    "rate",
    "subtotal",
    "total price"
]

    def looks_like_address(line):

        address_words = [
            "street",
            "st",
            "road",
            "rd",
            "drive",
            "dr",
            "avenue",
            "ave",
            "lane",
            "ln",
            "ny",
            "ca",
            "ma",
            "nyc",
            "usa",
            "place",
            "Palm",
            "po."
        ]


        lower = line.lower()


        if any(word == lower.strip() for word in SKIP_WORDS):
            return True


        # contains many numbers = probably address
        numbers = len(re.findall(r"\d+", line))

        if numbers >= 2:
            return True


        return False


    # Try labelled vendor first

    vendor_match = re.search(
        r"(?:vendor|supplier|company|seller|from|issued\s+by)"
        r"\s*[:\-]\s*(.+)",
        text,
        re.IGNORECASE
    )


    if vendor_match:

        candidate = vendor_match.group(1).strip()

        if not looks_like_address(candidate):

            data["vendor_name"] = candidate



    # fallback

    if data["vendor_name"] == "":

        for line in lines[:20]:

            lower = line.lower()


            if any(word in lower for word in SKIP_WORDS):
                continue


            if looks_like_address(line):
                continue


            # must contain letters
            if re.search("[A-Za-z]", line):

                data["vendor_name"] = line
                break

    return data
