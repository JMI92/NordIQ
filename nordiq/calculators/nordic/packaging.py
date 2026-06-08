"""Nordic Packaging EPR Calculator — implemented in build step 5."""

from nordiq.calculators.base import EPRCalculator, EPRObligation, ReportingPeriod
from nordiq.ingestion.base import NormalizedProductData
from nordiq.models.enums import ProductCategory


class NordicPackagingCalculator(EPRCalculator):
    """Calculates packaging EPR fees for FI/SE/NO/DK. Implemented in build step 5."""

    product_category = ProductCategory.PACKAGING

    def __init__(self, country: str):
        self.country_code = country.upper()

    def calculate(
        self,
        products: list[NormalizedProductData],
        reporting_period: ReportingPeriod,
    ) -> EPRObligation:
        raise NotImplementedError("NordicPackagingCalculator implemented in build step 5")
