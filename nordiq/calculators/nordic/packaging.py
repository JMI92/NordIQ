"""Nordic Packaging EPR Calculator.

Calculates packaging EPR fees for FI, SE, NO, DK.

Rates are injected at construction time (fetched from the epr_rates DB table by the
calling service layer) so the calculator itself has no database dependency and is
fully unit-testable with known inputs.

Rate lookup precedence (all handled by the service layer before calling calculate()):
  1. Most-specific rate valid on reporting_period.end for the given country + material
  2. "other" material rate as fallback when a specific material has no rate

All arithmetic uses Decimal — never float.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from nordiq.calculators.base import EPRCalculator, EPRObligation, ReportingPeriod
from nordiq.ingestion.base import NormalizedProductData
from nordiq.models.enums import MaterialType, ProductCategory


@dataclass
class RateSet:
    """EPR rates for one country, one product category, one reporting period."""
    country_code: str
    product_category: ProductCategory
    currency: str
    # material_type value (str) → rate per kg
    rates: dict[str, Decimal]
    valid_from: date
    valid_to: date | None = None
    regulation_reference: str = ""


class NordicPackagingCalculator(EPRCalculator):
    """Calculates packaging EPR fees for FI/SE/NO/DK.

    Construct with a RateSet whose rates cover all materials expected in the product
    list. If a product's material has no specific rate, the 'other' rate is used as
    fallback. If 'other' is also absent, calculate() raises ValueError.

    Example:
        rate_set = RateSet(
            country_code="FI",
            product_category=ProductCategory.PACKAGING,
            currency="EUR",
            rates={
                "plastic": Decimal("0.45"),
                "paper":   Decimal("0.08"),
                "glass":   Decimal("0.06"),
                "metal":   Decimal("0.12"),
                "wood":    Decimal("0.04"),
                "other":   Decimal("0.20"),
            },
            valid_from=date(2024, 1, 1),
        )
        calculator = NordicPackagingCalculator(rate_set)
        obligation = calculator.calculate(products, period)
    """

    product_category = ProductCategory.PACKAGING

    def __init__(self, rate_set: RateSet) -> None:
        self.country_code = rate_set.country_code.upper()
        self._rate_set = rate_set

    def calculate(
        self,
        products: list[NormalizedProductData],
        reporting_period: ReportingPeriod,
    ) -> EPRObligation:
        """Calculate the packaging EPR obligation for the given products and period.

        Only products whose reporting period overlaps with the given period are included.
        Weight is aggregated per material, then multiplied by the corresponding rate.
        """
        # Filter to products that fall within the reporting period
        in_scope = [
            p for p in products
            if p.reporting_period_start <= reporting_period.end
            and p.reporting_period_end >= reporting_period.start
        ]

        # Aggregate weight per material
        weight_by_material: dict[str, Decimal] = {}
        for product in in_scope:
            material_key = product.material_type.value
            w = Decimal(str(product.weight_kg))
            weight_by_material[material_key] = weight_by_material.get(material_key, Decimal(0)) + w

        # Calculate fee per material
        fee_by_material: dict[str, Decimal] = {}
        rates_used: dict[str, Decimal] = {}

        for material, weight in weight_by_material.items():
            rate = self._resolve_rate(material)
            fee = (weight * rate).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
            fee_by_material[material] = fee
            rates_used[material] = rate

        total_weight = sum(weight_by_material.values(), Decimal(0))
        total_fee = sum(fee_by_material.values(), Decimal(0)).quantize(
            Decimal("0.0001"), rounding=ROUND_HALF_UP
        )

        snapshot = {
            "calculator": "NordicPackagingCalculator",
            "country_code": self.country_code,
            "product_category": self.product_category.value,
            "reporting_period": {
                "start": reporting_period.start.isoformat(),
                "end": reporting_period.end.isoformat(),
            },
            "rate_set": {
                "valid_from": self._rate_set.valid_from.isoformat(),
                "valid_to": self._rate_set.valid_to.isoformat() if self._rate_set.valid_to else None,
                "regulation_reference": self._rate_set.regulation_reference,
                "currency": self._rate_set.currency,
            },
            "rates_used": {m: str(r) for m, r in rates_used.items()},
            "weight_by_material_kg": {m: str(w) for m, w in weight_by_material.items()},
            "fee_by_material": {m: str(f) for m, f in fee_by_material.items()},
            "total_weight_kg": str(total_weight),
            "total_fee": str(total_fee),
            "currency": self._rate_set.currency,
            "products_in_scope": len(in_scope),
            "products_total": len(products),
        }

        return EPRObligation(
            country_code=self.country_code,
            pro_id=f"nordic_pro_{self.country_code.lower()}",
            product_category=self.product_category,
            reporting_period=reporting_period,
            total_weight_kg=total_weight,
            fee_amount=total_fee,
            currency=self._rate_set.currency,
            weight_by_material={m: w for m, w in weight_by_material.items()},
            calculation_snapshot=snapshot,
        )

    def _resolve_rate(self, material: str) -> Decimal:
        rates = self._rate_set.rates
        if material in rates:
            return rates[material]
        if "other" in rates:
            return rates["other"]
        raise ValueError(
            f"No EPR rate for material '{material}' in {self.country_code} rate set, "
            "and no 'other' fallback rate is defined."
        )
