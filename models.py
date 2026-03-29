# models.py — Dataclasses for all structured data in the pipeline

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class AmountInfo:
    original: float
    currency: str                    # ISO code of bill currency
    converted: Optional[float]       # None if same currency
    base_currency: str               # ISO code of company currency
    exchange_rate: Optional[float]   # None if same currency


@dataclass
class ConfidenceScores:
    amount: float   # 0.0 – 1.0
    date: float     # 0.0 – 1.0


@dataclass
class ReceiptData:
    amount: AmountInfo
    date: Optional[str]              # ISO format: YYYY-MM-DD
    vendor: Optional[str]
    category: Optional[str]          # Provided by employee; null if not given
    payment_method: Optional[str]
    description: Optional[str]
    confidence: ConfidenceScores
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "amount": {
                "original": self.amount.original,
                "currency": self.amount.currency,
                "converted": self.amount.converted,
                "base_currency": self.amount.base_currency,
                "exchange_rate": self.amount.exchange_rate,
            },
            "date": self.date,
            "vendor": self.vendor,
            "category": self.category,
            "payment_method": self.payment_method,
            "description": self.description,
            "confidence": {
                "amount": self.confidence.amount,
                "date": self.confidence.date,
            },
            "warnings": self.warnings,
        }
