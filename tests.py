# tests.py — Unit tests for all receipt_processor modules

import sys
import os
import json
import unittest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(__file__))

from parser import extract_amount, extract_date, extract_vendor, extract_payment_method
from currency import resolve_bill_currency, detect_ocr_currency, check_currency_mismatch
from converter import convert_amount, get_exchange_rate
from normalizer import (
    normalize_currency_code, normalize_amount, normalize_date,
    normalize_vendor, normalize_payment_method, normalize_description,
)
from config import COUNTRY_TO_CURRENCY


# ===========================================================================
# Parser tests
# ===========================================================================

class TestExtractAmount(unittest.TestCase):

    def test_grand_total_label(self):
        text = "Subtotal: 120.00\nTax: 10.00\nGrand Total: 130.00"
        amount, conf = extract_amount(text)
        self.assertEqual(amount, 130.00)
        self.assertGreaterEqual(conf, 0.90)

    def test_total_label(self):
        text = "Item 1: 50.00\nItem 2: 30.00\nTotal: 80.00"
        amount, conf = extract_amount(text)
        self.assertEqual(amount, 80.00)
        self.assertGreaterEqual(conf, 0.90)

    def test_eu_number_format(self):
        text = "Gesamt: 1.234,56"
        amount, conf = extract_amount(text)
        self.assertEqual(amount, 1234.56)

    def test_amount_on_next_line(self):
        text = "TOTAL\n99.99\nThank you"
        amount, conf = extract_amount(text)
        self.assertEqual(amount, 99.99)
        self.assertGreaterEqual(conf, 0.70)

    def test_largest_number_fallback(self):
        text = "Coffee 3.50\nSandwich 7.25\nMuffin 2.00"
        amount, conf = extract_amount(text)
        self.assertEqual(amount, 7.25)
        self.assertEqual(conf, 0.50)

    def test_no_amount(self):
        text = "No numbers here at all."
        amount, conf = extract_amount(text)
        self.assertIsNone(amount)
        self.assertEqual(conf, 0.0)

    def test_amount_with_currency_symbol(self):
        text = "Total: $567.00"
        amount, conf = extract_amount(text)
        self.assertEqual(amount, 567.00)

    def test_amount_with_comma_thousands(self):
        text = "Grand Total: 1,250.00"
        amount, conf = extract_amount(text)
        self.assertEqual(amount, 1250.00)


class TestExtractDate(unittest.TestCase):

    def test_iso_format(self):
        date, conf = extract_date("Date: 2024-10-04")
        self.assertEqual(date, "2024-10-04")
        self.assertGreaterEqual(conf, 0.85)

    def test_dd_mm_yyyy(self):
        date, conf = extract_date("Date: 04-10-2024")
        self.assertEqual(date, "2024-10-04")

    def test_written_month(self):
        date, conf = extract_date("Invoice Date: 04 Oct 2024")
        self.assertEqual(date, "2024-10-04")

    def test_no_date(self):
        date, conf = extract_date("No date on this receipt.")
        self.assertIsNone(date)
        self.assertEqual(conf, 0.0)


class TestExtractVendor(unittest.TestCase):

    def test_first_line(self):
        text = "Starbucks\n123 Main Street\nDate: 2024-10-04\nTotal: 5.50"
        vendor = extract_vendor(text)
        self.assertEqual(vendor, "Starbucks")

    def test_skips_address(self):
        text = "123 Main Street\nCarrefour Dubai\nTotal: 150.00"
        vendor = extract_vendor(text)
        # Should skip the address line and pick Carrefour Dubai
        self.assertIn("Carrefour", vendor)

    def test_no_vendor(self):
        text = "123456\n789012\n0.00"
        vendor = extract_vendor(text)
        self.assertIsNone(vendor)


class TestExtractPaymentMethod(unittest.TestCase):

    def test_cash(self):
        self.assertEqual(extract_payment_method("Payment: Cash"), "Cash")

    def test_visa(self):
        self.assertEqual(extract_payment_method("Paid by Visa card"), "Visa")

    def test_upi(self):
        self.assertEqual(extract_payment_method("UPI transaction confirmed"), "UPI")

    def test_none(self):
        self.assertIsNone(extract_payment_method("No payment info here"))


# ===========================================================================
# Currency tests
# ===========================================================================

class TestResolveBillCurrency(unittest.TestCase):

    def test_known_country(self):
        currency, warnings = resolve_bill_currency("India")
        self.assertEqual(currency, "INR")
        self.assertEqual(warnings, [])

    def test_case_insensitive(self):
        currency, warnings = resolve_bill_currency("UAE")
        self.assertEqual(currency, "AED")

    def test_unknown_country(self):
        currency, warnings = resolve_bill_currency("Narnia")
        self.assertEqual(currency, "UNKNOWN")
        self.assertTrue(len(warnings) > 0)

    def test_usa_variants(self):
        for variant in ["USA", "us", "United States", "America"]:
            currency, _ = resolve_bill_currency(variant)
            self.assertEqual(currency, "USD", f"Failed for variant: {variant}")


class TestDetectOcrCurrency(unittest.TestCase):

    def test_detects_iso_code(self):
        text = "Total: USD 150.00"
        result = detect_ocr_currency(text)
        self.assertEqual(result, "USD")

    def test_detects_symbol(self):
        text = "Grand Total: €85.00"
        result = detect_ocr_currency(text)
        self.assertEqual(result, "EUR")

    def test_detects_inr_symbol(self):
        text = "Total ₹ 2500"
        result = detect_ocr_currency(text)
        self.assertEqual(result, "INR")

    def test_returns_none_when_no_currency(self):
        text = "Some text with no currency info."
        result = detect_ocr_currency(text)
        self.assertIsNone(result)

    def test_prefers_total_area(self):
        # AED appears near Total, USD appears elsewhere
        text = "Receipt from New York\nUSD rates apply\nGrand Total: AED 200.00"
        result = detect_ocr_currency(text)
        self.assertEqual(result, "AED")


class TestCheckCurrencyMismatch(unittest.TestCase):

    def test_no_mismatch(self):
        warnings = check_currency_mismatch("AED", "AED", "UAE")
        self.assertEqual(warnings, [])

    def test_mismatch_produces_warning(self):
        warnings = check_currency_mismatch("AED", "USD", "UAE")
        self.assertTrue(len(warnings) > 0)
        self.assertIn("USD", warnings[0])
        self.assertIn("AED", warnings[0])

    def test_unknown_ocr_no_warning(self):
        warnings = check_currency_mismatch("INR", None, "India")
        self.assertEqual(warnings, [])


# ===========================================================================
# Normalizer tests
# ===========================================================================

class TestNormalizers(unittest.TestCase):

    def test_currency_code_uppercase(self):
        self.assertEqual(normalize_currency_code("usd"), "USD")
        self.assertEqual(normalize_currency_code("Eur"), "EUR")

    def test_currency_code_invalid(self):
        self.assertIsNone(normalize_currency_code("US"))
        self.assertIsNone(normalize_currency_code("USDD"))
        self.assertIsNone(normalize_currency_code(None))

    def test_normalize_amount(self):
        self.assertEqual(normalize_amount(150.5678), 150.57)
        self.assertIsNone(normalize_amount(None))

    def test_normalize_date_valid(self):
        self.assertEqual(normalize_date("2024-10-04"), "2024-10-04")

    def test_normalize_date_invalid(self):
        self.assertIsNone(normalize_date("04/10/2024"))  # Not ISO
        self.assertIsNone(normalize_date(None))

    def test_normalize_vendor_title_case(self):
        self.assertEqual(normalize_vendor("STARBUCKS"), "Starbucks")

    def test_normalize_vendor_none(self):
        self.assertIsNone(normalize_vendor(None))
        self.assertIsNone(normalize_vendor(""))

    def test_normalize_description_truncate(self):
        long_desc = "x" * 400
        result = normalize_description(long_desc)
        self.assertEqual(len(result), 300)


# ===========================================================================
# Converter tests (mocked API)
# ===========================================================================

class TestConverter(unittest.TestCase):

    @patch("converter.requests.get")
    def test_successful_conversion(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"rates": {"INR": 83.25}}
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        converted, rate, warnings = convert_amount(100.0, "USD", "INR")
        self.assertEqual(converted, 8325.0)
        self.assertEqual(rate, 83.25)
        self.assertEqual(warnings, [])

    def test_same_currency_no_conversion(self):
        converted, rate, warnings = convert_amount(100.0, "INR", "INR")
        self.assertIsNone(converted)
        self.assertIsNone(rate)
        self.assertEqual(warnings, [])

    @patch("converter.requests.get")
    def test_api_timeout_warning(self, mock_get):
        import requests as req
        mock_get.side_effect = req.exceptions.Timeout

        converted, rate, warnings = convert_amount(100.0, "USD", "INR")
        self.assertIsNone(converted)
        self.assertTrue(len(warnings) > 0)
        self.assertIn("Timeout", warnings[0])

    @patch("converter.requests.get")
    def test_connection_error_warning(self, mock_get):
        import requests as req
        mock_get.side_effect = req.exceptions.ConnectionError

        converted, rate, warnings = convert_amount(100.0, "EUR", "INR")
        self.assertIsNone(converted)
        self.assertTrue(len(warnings) > 0)
        self.assertIn("Network error", warnings[0])


# ===========================================================================
# Config tests
# ===========================================================================

class TestConfig(unittest.TestCase):

    def test_all_values_are_3char_uppercase(self):
        for country, code in COUNTRY_TO_CURRENCY.items():
            self.assertEqual(len(code), 3, f"{country} → {code} is not 3 chars")
            self.assertEqual(code, code.upper(), f"{country} → {code} is not uppercase")

    def test_common_countries_present(self):
        for country in ["india", "usa", "uae", "germany", "australia"]:
            self.assertIn(country, COUNTRY_TO_CURRENCY, f"'{country}' missing from map")


# ===========================================================================
# Integration smoke test (no real file/API needed)
# ===========================================================================

class TestProcessorIntegration(unittest.TestCase):

    def setUp(self):
        # Clear the in-memory rate cache before each test to prevent bleed-through
        import converter
        converter._rate_cache.clear()

    @patch("processor.extract_text")
    @patch("converter.requests.get")
    def test_full_pipeline_usd_to_inr(self, mock_get, mock_ocr):
        mock_ocr.return_value = (
            "Starbucks\n"
            "123 Main St, New York\n"
            "Date: 2024-10-04\n"
            "Coffee          4.50\n"
            "Muffin          3.00\n"
            "Total:          7.50\n"
            "Paid by: Visa\n"
        )
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"rates": {"INR": 83.0}}
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        from processor import process_receipt
        result = process_receipt(
            file_path="dummy.jpg",
            bill_country="USA",
            company_country="India",
            category="Food & Beverage",
        )

        self.assertEqual(result["amount"]["currency"], "USD")
        self.assertEqual(result["amount"]["base_currency"], "INR")
        self.assertEqual(result["amount"]["original"], 7.50)
        self.assertAlmostEqual(result["amount"]["converted"], 622.5, delta=1.0)
        self.assertEqual(result["amount"]["exchange_rate"], 83.0)
        self.assertEqual(result["date"], "2024-10-04")
        self.assertEqual(result["vendor"], "Starbucks")
        self.assertEqual(result["category"], "Food & Beverage")
        self.assertEqual(result["payment_method"], "Visa")
        self.assertGreaterEqual(result["confidence"]["amount"], 0.90)
        self.assertEqual(result["warnings"], [])

    @patch("processor.extract_text")
    @patch("converter.requests.get")
    def test_currency_mismatch_warning(self, mock_get, mock_ocr):
        mock_ocr.return_value = (
            "Dubai Mall\n"
            "Date: 2024-11-01\n"
            "USD 200.00\n"       # OCR sees USD but employee said UAE (AED)
            "Total: 200.00\n"
        )
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"rates": {"INR": 22.67}}
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        from processor import process_receipt
        result = process_receipt(
            file_path="dummy.jpg",
            bill_country="UAE",
            company_country="India",
            category="Shopping",
        )

        self.assertEqual(result["amount"]["currency"], "AED")
        # Should have a mismatch warning
        self.assertTrue(
            any("USD" in w and "AED" in w for w in result["warnings"]),
            "Expected mismatch warning not found"
        )

    @patch("processor.extract_text")
    def test_same_currency_no_conversion(self, mock_ocr):
        mock_ocr.return_value = (
            "Reliance Fresh\n"
            "Date: 2024-12-01\n"
            "Total: ₹ 850.00\n"
        )
        from processor import process_receipt
        result = process_receipt(
            file_path="dummy.jpg",
            bill_country="India",
            company_country="India",
            category="Groceries",
        )
        # Same currency: converted == original, rate == 1.0
        self.assertEqual(result["amount"]["currency"], "INR")
        self.assertEqual(result["amount"]["base_currency"], "INR")
        self.assertEqual(result["amount"]["converted"], 850.0)
        self.assertEqual(result["amount"]["exchange_rate"], 1.0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
