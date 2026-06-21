"""Data normalisation utilities — implemented in build step 3."""


def validate_normalized_record(record) -> list[str]:
    """Validate a NormalizedProductData record and return a list of error messages."""
    errors = []
    if record.weight_kg is not None and float(record.weight_kg) < 0:
        errors.append(f"weight_kg must be non-negative, got {record.weight_kg}")
    if record.weight_kg == 0:
        errors.append("weight_kg is 0 — confirm this is intentional")
    if not record.external_product_id:
        errors.append("external_product_id is required")
    if not record.description:
        errors.append("description is required")
    return errors
