# parser.py — Extract structured fields from raw OCR text

import re
from datetime import datetime
from typing import Optional


# ---------------------------------------------------------------------------
# Amount extraction
# ---------------------------------------------------------------------------

# Labels that strongly indicate the final total
_TOTAL_LABELS = [
    r"grand\s*total",
    r"total\s*amount",
    r"amount\s*due",
    r"amount\s*payable",
    r"net\s*total",
    r"total\s*due",
    r"total",
    r"subtotal",
]

# Regex to match a number in either US (1,234.56) or EU (1.234,56) format
_NUMBER_RE = re.compile(
    r"""
    (?<!\d)                          # not preceded by digit
    (?:
        \d{1,3}(?:[.,]\d{3})+[.,]\d{2}  # 1,234.56 or 1.234,56
        |
        \d+[.,]\d{2}                     # 12.50 or 12,50
        |
        \d+                              # plain integer
    )
    (?!\d)                           # not followed by digit
    """,
    re.VERBOSE,
)


def _parse_number(raw: str) -> float:
    """
    Normalise a raw number string to a float.
    Handles both US format (1,234.56) and EU format (1.234,56).
    """
    raw = raw.strip()
    # EU format: last separator is a comma and prior separators are dots
    if re.match(r"^\d{1,3}(\.\d{3})+(,\d{2})$", raw):
        raw = raw.replace(".", "").replace(",", ".")
    else:
        raw = raw.replace(",", "")
    return float(raw)


def extract_amount(text: str) -> tuple[Optional[float], float]:
    """
    Extract the most likely total amount from OCR text.

    Strategy (priority order):
      1. Number on the same line as a high-priority total label
      2. Number on the line immediately after a total label
      3. Largest number found anywhere on the receipt

    Returns (amount, confidence) where confidence is 0.0–1.0.
    """
    lines = text.splitlines()

    # Build a single regex that matches any total label
    total_pattern = re.compile(
        r"(?:" + "|".join(_TOTAL_LABELS) + r")",
        re.IGNORECASE,
    )

    # --- Pass 1: same-line match ---
    for label_re in _TOTAL_LABELS:
        pattern = re.compile(
            r"(?:" + label_re + r")\s*[:\-]?\s*" + r"([^\d]*)(" + _NUMBER_RE.pattern + r")",
            re.IGNORECASE | re.VERBOSE,
        )
        for line in lines:
            m = pattern.search(line)
            if m:
                try:
                    return _parse_number(m.group(2)), 0.95
                except ValueError:
                    continue

    # --- Pass 2: label on one line, number on next ---
    for i, line in enumerate(lines):
        if total_pattern.search(line) and i + 1 < len(lines):
            nums = _NUMBER_RE.findall(lines[i + 1])
            if nums:
                try:
                    return _parse_number(nums[-1]), 0.80
                except ValueError:
                    pass

    # --- Pass 3: largest number fallback ---
    all_nums = _NUMBER_RE.findall(text)
    if all_nums:
        parsed = []
        for n in all_nums:
            try:
                parsed.append(_parse_number(n))
            except ValueError:
                continue
        if parsed:
            return max(parsed), 0.50

    return None, 0.0


# ---------------------------------------------------------------------------
# Date extraction
# ---------------------------------------------------------------------------

_DATE_PATTERNS: list[tuple[str, str]] = [
    # ISO: 2024-10-04
    (r"\b(\d{4}[-/]\d{2}[-/]\d{2})\b", "%Y-%m-%d"),
    # DD/MM/YYYY or DD-MM-YYYY
    (r"\b(\d{2}[-/]\d{2}[-/]\d{4})\b", "%d-%m-%Y"),
    # MM/DD/YYYY
    (r"\b(\d{2}/\d{2}/\d{4})\b", "%m/%d/%Y"),
    # 04 Oct 2024 / 4 October 2024
    (r"\b(\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{4})\b", "%d %b %Y"),
    # Oct 04, 2024 / October 4, 2024
    (r"\b((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{1,2},?\s+\d{4})\b", "%b %d %Y"),
]


def extract_date(text: str) -> tuple[Optional[str], float]:
    """
    Extract date from OCR text. Returns (ISO date string or None, confidence).
    """
    for pattern, fmt in _DATE_PATTERNS:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            raw = m.group(1).strip().rstrip(",")
            # Normalise separators for strptime
            raw_normalised = raw.replace("/", "-")
            # Try all format variants: original fmt, with %B (full month), with %b (abbrev)
            for f in [fmt, fmt.replace("%b", "%B"), fmt.replace("%B", "%b"),
                      fmt.replace("%d-%m-%Y", "%d/%m/%Y")]:
                for raw_try in [raw_normalised, raw]:
                    try:
                        dt = datetime.strptime(raw_try, f)
                        return dt.strftime("%Y-%m-%d"), 0.90
                    except ValueError:
                        continue
    return None, 0.0


# ---------------------------------------------------------------------------
# Vendor extraction
# ---------------------------------------------------------------------------

def extract_vendor(text: str) -> Optional[str]:
    """
    Heuristic: The vendor name is usually in the first 1–3 non-empty lines
    of the receipt, before any address or itemised list begins.
    """
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    candidates = []
    for line in lines[:5]:
        # Skip lines that look like addresses, phone numbers, or URLs
        if re.search(r"\d{5,}|www\.|\.com|tel:|ph:|@", line, re.IGNORECASE):
            continue
        # Skip lines that start with a number (likely an address like "123 Main St")
        if re.match(r"^\d", line):
            continue
        # Skip lines that are purely numbers or single characters
        if re.match(r"^[\d\W]+$", line) or len(line) < 3:
            continue
        candidates.append(line)

    return candidates[0] if candidates else None


# ---------------------------------------------------------------------------
# Payment method extraction
# ---------------------------------------------------------------------------

_PAYMENT_PATTERNS = [
    (r"\b(cash)\b", "Cash"),
    (r"\b(visa)\b", "Visa"),
    (r"\b(mastercard|master card)\b", "Mastercard"),
    (r"\b(amex|american express)\b", "Amex"),
    (r"\b(credit\s*card)\b", "Credit Card"),
    (r"\b(debit\s*card)\b", "Debit Card"),
    (r"\b(upi|gpay|google pay|phonepe|paytm)\b", "UPI"),
    (r"\b(card)\b", "Card"),
    (r"\b(net\s*banking|netbanking)\b", "Net Banking"),
    (r"\b(wallet)\b", "Wallet"),
]


def extract_payment_method(text: str) -> Optional[str]:
    for pattern, label in _PAYMENT_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            return label
    return None


# ---------------------------------------------------------------------------
# Description fallback
# ---------------------------------------------------------------------------

def extract_description(text: str) -> str:
    """
    Build a short description from the first meaningful lines of OCR text.
    Used as a fallback summary when other fields are sparse.
    """
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    # Take up to 3 non-trivial lines
    snippet_lines = [l for l in lines if len(l) > 4][:3]
    return " | ".join(snippet_lines) if snippet_lines else "Receipt"
