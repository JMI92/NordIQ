"""Calculator registry — maps (country_code, ProductCategory) to a calculator factory.

Factories (not instances) are stored so each call gets a fresh calculator configured
with the current rate set fetched from the database.

Usage (service layer):
    from uusio.calculators.registry import get_calculator_class
    from uusio.calculators.nordic.packaging import RateSet

    CalcClass = get_calculator_class("FI", ProductCategory.PACKAGING)
    calc = CalcClass(rate_set)
    obligation = calc.calculate(products, period)
"""

from uusio.models.enums import ProductCategory

# Key: (country_code: str, ProductCategory) → calculator class
_REGISTRY: dict[tuple[str, ProductCategory], type] = {}


def register(country_code: str, product_category: ProductCategory):
    """Class decorator that registers a calculator in the global registry."""
    def decorator(cls):
        _REGISTRY[(country_code.upper(), product_category)] = cls
        return cls
    return decorator


def get_calculator_class(country_code: str, product_category: ProductCategory) -> type:
    """Return the calculator class for the given country and category."""
    key = (country_code.upper(), product_category)
    cls = _REGISTRY.get(key)
    if cls is None:
        available = [(c, cat.value) for c, cat in _REGISTRY]
        raise ValueError(
            f"No calculator registered for country={country_code}, "
            f"category={product_category.value}. Available: {available}"
        )
    return cls


def get_calculator(country_code: str, product_category: ProductCategory):
    """Return an uninstantiated calculator class (backwards-compatible alias)."""
    return get_calculator_class(country_code, product_category)


# ---------------------------------------------------------------------------
# Register built-in calculators
# ---------------------------------------------------------------------------
# Import here (bottom of file) to avoid circular imports.
from uusio.calculators.nordic.packaging import NordicPackagingCalculator  # noqa: E402

for _country in ("FI", "SE", "NO", "DK"):
    _REGISTRY[(_country, ProductCategory.PACKAGING)] = NordicPackagingCalculator
