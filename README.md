# Receipt Processor

A modular Python pipeline that extracts structured data from receipt images/PDFs,
resolves the bill currency from employee input, and converts the total amount to
the company's base currency using live exchange rates.

---

## Architecture

```
receipt_processor/
├── config.py       # Country → currency mapping + symbol/code tables
├── models.py       # Dataclasses: ReceiptData, AmountInfo, ConfidenceScores
├── ocr.py          # Image preprocessing (OpenCV) + Tesseract OCR
├── parser.py       # Extract amount, date, vendor, payment method
├── currency.py     # Country → currency resolution + OCR sanity check
├── converter.py    # Live exchange rate fetch (frankfurter.app) + conversion
├── normalizer.py   # Standardise all fields (ISO dates, uppercase codes, etc.)
├── processor.py    # Main orchestrator — single entry point
└── tests.py        # 48 unit + integration tests
```

---

## Installation

```bash
# System dependencies
apt-get install tesseract-ocr poppler-utils

# Python dependencies
pip install pytesseract Pillow opencv-python-headless pdf2image requests
```

---

## Usage

### As a Python module

```python
from processor import process_receipt

result = process_receipt(
    file_path="receipt.jpg",        # image or PDF
    bill_country="UAE",             # where the bill is from (employee input)
    company_country="India",        # where the company is based (system config)
    category="Travel",              # expense category (employee input, optional)
)

print(result)
```

### From the command line

```bash
python processor.py receipt.jpg \
  --bill-country "UAE" \
  --company-country "India" \
  --category "Travel"
```

---

## Output Schema

```json
{
  "amount": {
    "original": 200.0,
    "currency": "AED",
    "converted": 4534.0,
    "base_currency": "INR",
    "exchange_rate": 22.67
  },
  "date": "2024-10-04",
  "vendor": "Carrefour Dubai",
  "category": "Travel",
  "payment_method": "Visa",
  "description": "Carrefour Dubai | Date: 2024-10-04 | Total: AED 200.00",
  "confidence": {
    "amount": 0.95,
    "date": 0.9
  },
  "warnings": []
}
```

### Field notes

| Field | Source | Notes |
|---|---|---|
| `amount.original` | OCR | Extracted from receipt |
| `amount.currency` | Employee input → `bill_country` | Country-to-currency mapped |
| `amount.converted` | Live API | `null` if same currency as base |
| `amount.base_currency` | Caller → `company_country` | Country-to-currency mapped |
| `amount.exchange_rate` | frankfurter.app | `1.0` if same currency, `null` if conversion failed |
| `date` | OCR | ISO 8601 format (YYYY-MM-DD) |
| `vendor` | OCR | First meaningful line of receipt |
| `category` | Employee input | Stored as-is; `null` if not provided |
| `payment_method` | OCR | Detected from keywords (Visa, Cash, UPI…) |
| `description` | OCR | First 3 non-trivial lines as fallback summary |
| `confidence.amount` | Parser | 0.95 = near "Total" label, 0.50 = largest number |
| `confidence.date` | Parser | 0.90 = pattern matched, 0.0 = not found |
| `warnings` | All layers | Non-fatal issues (mismatch, unknown country, API errors) |

---

## Currency Resolution Logic

The employee-provided `bill_country` is the **source of truth** for currency.

```
Employee: "UAE"  →  config.py  →  "AED"
```

OCR currency detection is run as a **secondary sanity check only**.
If OCR finds a different currency than what the country maps to,
a warning is added to the output but the employee's input is still used.

### Example warning
```
"OCR detected currency 'USD' on the receipt, but employee selected
 country 'UAE' which maps to 'AED'. Using 'AED' as provided.
 Please verify if this is correct."
```

---

## Amount Extraction Priority

1. Number on the same line as `Grand Total` / `Total Amount` / `Amount Due`
2. Number on the line immediately after a total label
3. Largest number found anywhere on the receipt (lowest confidence)

Handles both US format (`1,234.56`) and EU format (`1.234,56`).

---

## Currency Conversion

- API: [frankfurter.app](https://www.frankfurter.app) — free, no API key, ECB-backed
- Rates are cached in-memory for 1 hour to avoid redundant API calls
- If the API is unreachable, a warning is added and `converted` is `null`
- If `bill_country` and `company_country` map to the same currency, conversion is skipped

---

## Supported Countries

100+ countries mapped in `config.py`, covering Asia, Middle East, Europe,
Americas, Africa, and Oceania. To add a missing country:

```python
# config.py
COUNTRY_TO_CURRENCY["country name lowercase"] = "ISO_CODE"
```

---

## Running Tests

```bash
python tests.py
# Ran 48 tests in ~1.2s — OK
```

Tests cover: amount/date/vendor/payment extraction, currency resolution,
OCR mismatch detection, normalisation, converter (mocked API), and 3 end-to-end
integration scenarios.

---

## Edge Cases Handled

| Case | Handling |
|---|---|
| No currency symbol on receipt | OCR check skipped; falls back to employee country |
| Multiple currencies on receipt | Prefer currency nearest to "Total" label |
| EU number format (`1.234,56`) | Regex detects and converts to float correctly |
| Blurry / low-res image | OpenCV upscaling + denoising before OCR |
| Skewed / rotated receipt | Deskew via Hough transform |
| PDF input | Converted to images via pdf2image (poppler) |
| Same source and base currency | Conversion skipped; rate set to 1.0 |
| API timeout / network failure | Warning added; `converted` set to `null` |
| Unknown country mapping | Warning added; currency set to `"UNKNOWN"` |
| Missing amount | Warning added; `original` set to `null` |
