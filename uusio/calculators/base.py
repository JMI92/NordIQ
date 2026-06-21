"""Abstract EPR calculator interface — implemented in build step 5."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from uusio.ingestion.base import NormalizedProductData
from uusio.models.enums import ProductCategory


@dataclass
class ReportingPeriod:
    start: date
    end: date


@dataclass
class EPRObligation:
    """Result of a calculation run — not the ORM model."""
    country_code: str
    pro_id: str
    product_category: ProductCategory
    reporting_period: ReportingPeriod
    total_weight_kg: Decimal
    fee_amount: Decimal
    currency: str
    weight_by_material: dict[str, Decimal]
    calculation_snapshot: dict  # all inputs + rates for immutable audit record


class EPRCalculator(ABC):
    country_code: str
    product_category: ProductCategory

    @abstractmethod
    def calculate(
        self,
        products: list[NormalizedProductData],
        reporting_period: ReportingPeriod,
    ) -> EPRObligation:
        """Calculate EPR obligations for the given products and period."""
        ...
