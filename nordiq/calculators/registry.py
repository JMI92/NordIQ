"""Calculator registry — maps (country_code, ProductCategory) to a calculator instance."""

from nordiq.models.enums import ProductCategory

# Populated in build step 5 when Nordic calculators are implemented.
# Key: (country_code: str, ProductCategory)
CALCULATORS: dict[tuple[str, ProductCategory], object] = {}


def get_calculator(country_code: str, product_category: ProductCategory):
    """Return the registered calculator for the given country and category."""
    key = (country_code.upper(), product_category)
    calculator = CALCULATORS.get(key)
    if calculator is None:
        raise ValueError(
            f"No calculator registered for country={country_code}, category={product_category}. "
            "Ensure build step 5 has been completed and the calculator is registered."
        )
    return calculator
