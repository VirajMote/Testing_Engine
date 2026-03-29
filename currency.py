# currency.py — Country → currency resolution + OCR sanity check

import re
from typing import Optional

from config import (
    COUNTRY_TO_CURRENCY,
    KNOWN_CURRENCY_CODES,
    SYMBOL_TO_CURRENCIES,
)


def resolve_bill_currency(bill_country: str) -> tuple[str, list[str]]:
    """
    Map the employee-provided bill country to an ISO currency code.

    Returns:
        (currency_code, warnings)
        If the country is not found in our mapping, returns ("UNKNOWN", [warning]).
    """
    warnings: list[str] = []
    key = bill_country.strip().lower()

    currency = COUNTRY_TO_CURRENCY.get(key)
    if not currency:
        warnings.append(
            f"Could not map bill country '{bill_country}' to a known currency. "
            f"Please verify the currency manually."
        )
        return "UNKNOWN", warnings

    return currency, warnings


def detect_ocr_currency(text: str) -> Optional[str]:
    """
    Best-effort detection of currency from OCR text.
    Used ONLY as a sanity check against the employee-provided country.

    Priority:
      1. ISO currency code (e.g. "USD", "INR")
      2. Currency symbol (e.g. "$", "€", "₹")

    Returns the most likely ISO code, or None if not found.
    """
    # 1. Look for explicit ISO codes
    # Search near "Total" first, then anywhere
    total_area = _extract_total_area(text)
    for search_zone in [total_area, text]:
        if not search_zone:
            continue
        found_codes = _find_iso_codes(search_zone)
        if found_codes:
            return found_codes[0]  # Return the first/most prominent match

    # 2. Look for currency symbols
    for symbol, candidates in SYMBOL_TO_CURRENCIES.items():
        if symbol in text:
            return candidates[0]  # Return the most common currency for this symbol

    return None


def check_currency_mismatch(
    employee_currency: str,
    ocr_currency: Optional[str],
    bill_country: str,
) -> list[str]:
    """
    Compare OCR-detected currency against employee-provided country currency.
    Returns a list of warning strings (empty if no mismatch).
    """
    warnings: list[str] = []

    if not ocr_currency or ocr_currency == "UNKNOWN":
        return warnings  # Can't compare, no warning needed

    if employee_currency == "UNKNOWN":
        return warnings  # Already warned about unknown country

    if ocr_currency != employee_currency:
        warnings.append(
            f"OCR detected currency '{ocr_currency}' on the receipt, "
            f"but employee selected country '{bill_country}' which maps to '{employee_currency}'. "
            f"Using '{employee_currency}' as provided. Please verify if this is correct."
        )

    return warnings


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _extract_total_area(text: str) -> str:
    """
    Extract the portion of text near 'Total' or 'Grand Total' labels.
    This helps prioritise currency codes that appear next to the final amount.
    """
    pattern = re.compile(
        r"(?:grand\s*total|total\s*amount|amount\s*due|total)[^\n]{0,80}",
        re.IGNORECASE,
    )
    matches = pattern.findall(text)
    return " ".join(matches)


def _find_iso_codes(text: str) -> list[str]:
    """
    Find all known ISO currency codes in a text string.
    Returns them in order of appearance.
    """
    found: list[str] = []
    # Match 3-letter uppercase sequences that are known currency codes
    for m in re.finditer(r"\b([A-Z]{3})\b", text):
        code = m.group(1)
        if code in KNOWN_CURRENCY_CODES and code not in found:
            found.append(code)
    return found
