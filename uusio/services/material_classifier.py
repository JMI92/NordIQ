"""AI-powered EPR material classification using Claude."""

from __future__ import annotations

import json
import logging

from uusio.core.config import get_settings

logger = logging.getLogger(__name__)

MATERIAL_TYPES = [
    "rigid_plastic", "flexible_plastic", "single_use_plastic", "plastic",
    "paper", "glass", "metal", "wood", "beverage_carton", "composite",
    "electronics", "battery", "other",
]

PRODUCT_CATEGORIES = ["packaging", "weee", "batteries", "vehicles", "other"]

SYSTEM_PROMPT = """
You are an EPR (Extended Producer Responsibility) compliance expert with deep knowledge
of EU packaging regulations, WEEE directive, battery regulation, and PPWR.

Given a product name and description, return a JSON object with:
- category: the primary EPR category (packaging, weee, batteries, vehicles, other)
- materials: array of material components, each with:
  - material_type: one of: rigid_plastic, flexible_plastic, single_use_plastic, plastic,
    paper, glass, metal, wood, beverage_carton, composite, electronics, battery, other
  - weight_per_unit_kg: estimated weight in kg (float, can be small e.g. 0.005 for labels)
  - is_packaging: true if this is packaging material, false if it's the product itself
  - notes: brief reason for classification
- confidence: 0.0-1.0 how confident you are
- reasoning: one sentence explaining the main classification decision

Rules:
- Always include packaging materials separately from the product itself
- For WEEE products, include the electronics component
- Weights are estimates — use typical industry values
- If the product is purely packaging (e.g. a cardboard box), all materials have is_packaging=true
- Return ONLY valid JSON, no markdown, no explanation outside the JSON
""".strip()


async def classify_product(
    name: str,
    description: str,
    category_hint: str | None = None,
) -> dict:
    """Call Claude to classify a product's EPR materials.

    Returns a dict with keys: category, materials, confidence, reasoning.
    Raises on API error so caller can decide whether to skip or abort.
    """
    settings = get_settings()
    if not settings.anthropic_api_key:
        raise RuntimeError("ANTHROPIC_API_KEY not configured")

    try:
        import anthropic
    except ImportError:
        raise RuntimeError("anthropic package not installed")

    client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)

    user_content = f"Product name: {name}\nDescription: {description}"
    if category_hint:
        user_content += f"\nCategory hint: {category_hint}"

    message = await client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=1024,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_content}],
    )

    raw = message.content[0].text.strip()
    # Strip markdown code fences if present
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    result = json.loads(raw)

    # Validate and clamp
    result["confidence"] = float(result.get("confidence", 0.8))
    for mat in result.get("materials", []):
        if mat.get("material_type") not in MATERIAL_TYPES:
            mat["material_type"] = "other"
        mat["weight_per_unit_kg"] = max(0.0, float(mat.get("weight_per_unit_kg", 0.0)))
        mat["is_packaging"] = bool(mat.get("is_packaging", False))

    return result


async def classify_products_batch(
    products: list[dict],
) -> list[dict]:
    """Classify multiple products concurrently (max 5 at a time to avoid rate limits)."""
    import asyncio

    semaphore = asyncio.Semaphore(5)

    async def _classify_one(p: dict) -> dict:
        async with semaphore:
            try:
                result = await classify_product(
                    name=p.get("name", ""),
                    description=p.get("description", p.get("name", "")),
                    category_hint=p.get("category"),
                )
                return {"sku": p["sku"], "result": result, "error": None}
            except Exception as exc:
                logger.warning("Classification failed for %s: %s", p.get("sku"), exc)
                return {"sku": p["sku"], "result": None, "error": str(exc)}

    return await asyncio.gather(*[_classify_one(p) for p in products])
