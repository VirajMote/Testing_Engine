# converter.py — Live currency conversion via frankfurter.app

import time
from typing import Optional

import requests

# ---------------------------------------------------------------------------
# Simple in-memory rate cache (TTL: 1 hour)
# Avoids hammering the API when processing multiple receipts in one session.
# ---------------------------------------------------------------------------
_rate_cache: dict[str, tuple[float, float]] = {}  # key → (rate, timestamp)
_CACHE_TTL = 3600  # seconds


def get_exchange_rate(from_currency: str, to_currency: str) -> tuple[float, list[str]]:
    """
    Fetch the live exchange rate from frankfurter.app.
    Falls back to a cached rate if the API is unreachable.

    Returns:
        (exchange_rate, warnings)
        exchange_rate = 1.0 if same currency or on error (with warning).
    """
    warnings: list[str] = []

    # Same currency — no conversion needed
    if from_currency == to_currency:
        return 1.0, warnings

    if from_currency == "UNKNOWN":
        warnings.append(
            "Bill currency is UNKNOWN — cannot perform conversion. "
            "Converted amount is not available."
        )
        return 0.0, warnings

    cache_key = f"{from_currency}_{to_currency}"
    cached = _rate_cache.get(cache_key)
    if cached:
        rate, ts = cached
        if time.time() - ts < _CACHE_TTL:
            return rate, warnings

    # Live API call
    try:
        url = f"https://api.frankfurter.app/latest"
        params = {"from": from_currency, "to": to_currency}
        resp = requests.get(url, params=params, timeout=5)
        resp.raise_for_status()
        data = resp.json()
        rate = data["rates"][to_currency]
        _rate_cache[cache_key] = (rate, time.time())
        return rate, warnings

    except requests.exceptions.ConnectionError:
        warnings.append(
            f"Network error fetching exchange rate for {from_currency} → {to_currency}. "
            f"Converted amount is not available."
        )
    except requests.exceptions.Timeout:
        warnings.append(
            f"Timeout fetching exchange rate for {from_currency} → {to_currency}. "
            f"Converted amount is not available."
        )
    except (KeyError, ValueError) as e:
        warnings.append(
            f"Unexpected API response for {from_currency} → {to_currency}: {e}. "
            f"Converted amount is not available."
        )
    except requests.exceptions.HTTPError as e:
        warnings.append(
            f"API error fetching exchange rate for {from_currency} → {to_currency}: {e}. "
            f"Converted amount is not available."
        )

    return 0.0, warnings


def convert_amount(
    amount: float,
    from_currency: str,
    to_currency: str,
) -> tuple[Optional[float], Optional[float], list[str]]:
    """
    Convert an amount from one currency to another.

    Returns:
        (converted_amount, exchange_rate, warnings)
        converted_amount is None if conversion failed or currencies are the same.
        exchange_rate is None if same currency (no conversion needed).
    """
    # Same currency — skip conversion entirely
    if from_currency == to_currency:
        return None, None, []

    rate, warnings = get_exchange_rate(from_currency, to_currency)

    if rate == 0.0:
        # Conversion failed — warnings already populated
        return None, None, warnings

    converted = round(amount * rate, 2)
    return converted, rate, warnings
