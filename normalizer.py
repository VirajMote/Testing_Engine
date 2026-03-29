# normalizer.py — Standardise extracted fields before final output

import re
from typing import Optional


def normalize_currency_code(code: Optional[str]) -> Optional[str]:
    """
    Ensure currency code is uppercase ISO 4217 format (e.g. 'usd' → 'USD').
    Returns None if input is None or empty.
    """
    if not code:
        return None
    cleaned = code.strip().upper()
    # Must be exactly 3 alphabetic characters
    if re.match(r"^[A-Z]{3}$", cleaned):
        return cleaned
    return None


def normalize_amount(amount: Optional[float], decimal_places: int = 2) -> Optional[float]:
    """
    Round amount to a consistent number of decimal places.
    Returns None if input is None.
    """
    if amount is None:
        return None
    return round(amount, decimal_places)


def normalize_date(date_str: Optional[str]) -> Optional[str]:
    """
    Ensure date is in ISO format (YYYY-MM-DD).
    Accepts dates already in ISO format from the parser.
    Returns None if input is None or empty.
    """
    if not date_str:
        return None
    # Basic ISO format check
    if re.match(r"^\d{4}-\d{2}-\d{2}$", date_str.strip()):
        return date_str.strip()
    return None


def normalize_vendor(vendor: Optional[str]) -> Optional[str]:
    """
    Clean up vendor name:
      - Strip leading/trailing whitespace
      - Collapse multiple spaces
      - Title-case if all caps (e.g. "STARBUCKS" → "Starbucks")
    """
    if not vendor:
        return None
    cleaned = " ".join(vendor.split())
    if cleaned.isupper():
        cleaned = cleaned.title()
    return cleaned if cleaned else None


def normalize_payment_method(method: Optional[str]) -> Optional[str]:
    """Strip and return payment method, or None if empty."""
    if not method:
        return None
    return method.strip() or None


def normalize_description(description: Optional[str]) -> Optional[str]:
    """Trim and truncate description to a max of 300 characters."""
    if not description:
        return None
    cleaned = description.strip()
    return cleaned[:300] if cleaned else None
