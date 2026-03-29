# processor.py — Main orchestrator: single entry point for the full pipeline

import json
from typing import Optional

from ocr import extract_text
from parser import (
    extract_amount,
    extract_date,
    extract_description,
    extract_payment_method,
    extract_vendor,
)
from currency import (
    check_currency_mismatch,
    detect_ocr_currency,
    resolve_bill_currency,
)
from converter import convert_amount
from normalizer import (
    normalize_amount,
    normalize_currency_code,
    normalize_date,
    normalize_description,
    normalize_payment_method,
    normalize_vendor,
)
from models import AmountInfo, ConfidenceScores, ReceiptData
from config import COUNTRY_TO_CURRENCY


def process_receipt(
    file_path: str,
    bill_country: str,
    company_country: str,
    category: Optional[str] = None,
) -> dict:
    """
    Full receipt processing pipeline.

    Args:
        file_path:       Path to the receipt image or PDF.
        bill_country:    Country where the bill was issued (from employee).
        company_country: Country the company is based in (from caller/system).
        category:        Expense category provided by employee (optional).

    Returns:
        A dict matching the agreed output schema.
    """
    all_warnings: list[str] = []

    # ------------------------------------------------------------------
    # LAYER 1: OCR
    # ------------------------------------------------------------------
    raw_text = extract_text(file_path)

    # ------------------------------------------------------------------
    # LAYER 2: Field extraction
    # ------------------------------------------------------------------
    raw_amount, amount_confidence = extract_amount(raw_text)
    raw_date, date_confidence = extract_date(raw_text)
    raw_vendor = extract_vendor(raw_text)
    raw_payment = extract_payment_method(raw_text)
    raw_description = extract_description(raw_text)

    if raw_amount is None:
        all_warnings.append(
            "Could not extract a total amount from the receipt. "
            "Please enter the amount manually."
        )

    # ------------------------------------------------------------------
    # LAYER 3: Currency resolution (employee input is source of truth)
    # ------------------------------------------------------------------
    bill_currency, currency_warnings = resolve_bill_currency(bill_country)
    all_warnings.extend(currency_warnings)

    company_currency = _resolve_company_currency(company_country, all_warnings)

    # ------------------------------------------------------------------
    # LAYER 4: OCR currency sanity check
    # ------------------------------------------------------------------
    ocr_currency = detect_ocr_currency(raw_text)
    mismatch_warnings = check_currency_mismatch(bill_currency, ocr_currency, bill_country)
    all_warnings.extend(mismatch_warnings)

    # ------------------------------------------------------------------
    # LAYER 5: Currency conversion
    # ------------------------------------------------------------------
    normalized_amount = normalize_amount(raw_amount)
    converted_amount = None
    exchange_rate = None

    if normalized_amount is not None and bill_currency != "UNKNOWN":
        converted_amount, exchange_rate, conv_warnings = convert_amount(
            normalized_amount, bill_currency, company_currency
        )
        all_warnings.extend(conv_warnings)

        # Same currency — set converted = original for clarity
        if bill_currency == company_currency:
            converted_amount = normalized_amount
            exchange_rate = 1.0

    # ------------------------------------------------------------------
    # LAYER 6: Normalisation
    # ------------------------------------------------------------------
    final_currency = normalize_currency_code(bill_currency)
    final_base_currency = normalize_currency_code(company_currency)
    final_date = normalize_date(raw_date)
    final_vendor = normalize_vendor(raw_vendor)
    final_payment = normalize_payment_method(raw_payment)
    final_description = normalize_description(raw_description)
    final_category = category.strip() if category and category.strip() else None

    # ------------------------------------------------------------------
    # LAYER 7: Assemble output
    # ------------------------------------------------------------------
    amount_info = AmountInfo(
        original=normalized_amount,
        currency=final_currency or "UNKNOWN",
        converted=normalize_amount(converted_amount),
        base_currency=final_base_currency or "UNKNOWN",
        exchange_rate=round(exchange_rate, 6) if exchange_rate is not None else None,
    )

    confidence = ConfidenceScores(
        amount=round(amount_confidence, 2),
        date=round(date_confidence, 2),
    )

    receipt = ReceiptData(
        amount=amount_info,
        date=final_date,
        vendor=final_vendor,
        category=final_category,
        payment_method=final_payment,
        description=final_description,
        confidence=confidence,
        warnings=all_warnings,
    )

    return receipt.to_dict()


# ---------------------------------------------------------------------------
# Internal helper
# ---------------------------------------------------------------------------

def _resolve_company_currency(company_country: str, warnings: list[str]) -> str:
    """
    Map the company's home country to its currency code.
    Appends a warning if the country is not in our mapping.
    """
    key = company_country.strip().lower()
    currency = COUNTRY_TO_CURRENCY.get(key)
    if not currency:
        warnings.append(
            f"Could not map company country '{company_country}' to a known currency. "
            f"Defaulting base currency to 'UNKNOWN'. Please verify."
        )
        return "UNKNOWN"
    return currency


# ---------------------------------------------------------------------------
# CLI convenience
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Process a receipt image or PDF.")
    parser.add_argument("file", help="Path to receipt image or PDF")
    parser.add_argument("--bill-country", required=True, help="Country where the bill was issued")
    parser.add_argument("--company-country", required=True, help="Country the company is based in")
    parser.add_argument("--category", default=None, help="Expense category (optional)")
    args = parser.parse_args()

    result = process_receipt(
        file_path=args.file,
        bill_country=args.bill_country,
        company_country=args.company_country,
        category=args.category,
    )
    print(json.dumps(result, indent=2))
