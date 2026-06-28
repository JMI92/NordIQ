"""EPR regulation monitor — periodically fetches updates from official sources.

Sources checked:
- EUR-Lex (EU legislation feed)
- Finnish Environment Institute (SYKE) RSS
- Swedish EPA (Naturvårdsverket) news
- Norwegian Environment Agency
- Danish EPA (Miljøstyrelsen)
- German Federal Environment Agency (UBA)

Run weekly (Sundays 06:00 UTC) via APScheduler.
New or changed regulations are upserted into regulation_entries.
Urgent items (effective within 90 days) are tagged "urgent".
Gap analysis flags country+category combos with active PRO contracts but no regulation.
"""

from __future__ import annotations

import hashlib
import logging
import re
from datetime import date, datetime, timedelta
from typing import TypedDict
from xml.etree import ElementTree

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from uusio.models.pro_registry import CustomerPRORegistration, PROOrganisation
from uusio.models.regulation import RegulationEntry

logger = logging.getLogger(__name__)

URGENCY_DAYS = 90   # effective_date within this many days → "urgent"
RATE_STALE_DAYS = 180  # warn if EPR rates haven't been updated in this many days


class RegulationItem(TypedDict):
    country_code: str
    category: str
    title: str
    summary: str
    source_url: str
    tags: list[str]
    effective_date: date | None


# ---------------------------------------------------------------------------
# RSS / Atom feed parser
# ---------------------------------------------------------------------------

def _parse_rss(xml_text: str, country_code: str, category: str, tags: list[str]) -> list[RegulationItem]:
    """Parse an RSS 2.0 or Atom feed and return regulation items."""
    items: list[RegulationItem] = []
    try:
        root = ElementTree.fromstring(xml_text)
    except ElementTree.ParseError as e:
        logger.warning("Failed to parse XML feed: %s", e)
        return items

    ns = {"atom": "http://www.w3.org/2005/Atom"}

    # RSS 2.0
    for item in root.iter("item"):
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        desc = (item.findtext("description") or "").strip()
        pub_date_str = item.findtext("pubDate") or ""
        if not title or not link:
            continue
        items.append(RegulationItem(
            country_code=country_code,
            category=category,
            title=title[:500],
            summary=_clean_html(desc)[:2000] or title,
            source_url=link,
            tags=list(tags),
            effective_date=_parse_date_loose(pub_date_str),
        ))

    # Atom
    for entry in root.findall("atom:entry", ns):
        title = (entry.findtext("atom:title", namespaces=ns) or "").strip()
        link_el = entry.find("atom:link", ns)
        link = (link_el.get("href") if link_el is not None else "") or ""
        summary = (entry.findtext("atom:summary", namespaces=ns) or "").strip()
        updated = entry.findtext("atom:updated", namespaces=ns) or ""
        if not title or not link:
            continue
        items.append(RegulationItem(
            country_code=country_code,
            category=category,
            title=title[:500],
            summary=_clean_html(summary)[:2000] or title,
            source_url=link,
            tags=list(tags),
            effective_date=_parse_date_loose(updated),
        ))

    return items


def _clean_html(text: str) -> str:
    return re.sub(r"<[^>]+>", "", text).strip()


def _parse_date_loose(s: str) -> date | None:
    for fmt in ("%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S%z", "%a, %d %b %Y %H:%M:%S %z", "%Y-%m-%d"):
        try:
            return datetime.strptime(s[:25], fmt).date()
        except (ValueError, TypeError):
            continue
    return None


def _tag_urgency(item: RegulationItem) -> RegulationItem:
    """Add 'urgent' tag if effective_date is within URGENCY_DAYS from today."""
    if item["effective_date"] is None:
        return item
    today = date.today()
    if today <= item["effective_date"] <= today + timedelta(days=URGENCY_DAYS):
        if "urgent" not in item["tags"]:
            item["tags"] = item["tags"] + ["urgent"]
    return item


# ---------------------------------------------------------------------------
# Feed sources
# ---------------------------------------------------------------------------

SOURCES = [
    {
        "url": "https://eur-lex.europa.eu/rss/rss-notifications.xml?language=EN&subject=environmental_legislation",
        "country_code": "EU",
        "category": "Packaging",
        "tags": ["EUR-Lex", "EU", "EPR"],
    },
    {
        "url": "https://eur-lex.europa.eu/search.html?type=quick&lang=en&term=packaging+producer+responsibility&format=rss",
        "country_code": "EU",
        "category": "Packaging",
        "tags": ["EUR-Lex", "PPWR", "packaging"],
    },
    {
        "url": "https://www.naturvardsverket.se/rss/nyheter.xml",
        "country_code": "SE",
        "category": "Packaging",
        "tags": ["Sweden", "Naturvårdsverket", "EPR"],
    },
    {
        "url": "https://www.syke.fi/fi-FI/Rss/Uutiset",
        "country_code": "FI",
        "category": "Packaging",
        "tags": ["Finland", "SYKE", "EPR"],
    },
    {
        "url": "https://www.miljodirektoratet.no/rss/nyheter/",
        "country_code": "NO",
        "category": "Packaging",
        "tags": ["Norway", "Miljødirektoratet", "EPR"],
    },
    {
        "url": "https://mst.dk/service/nyheder/nyhedsarkiv/rss/",
        "country_code": "DK",
        "category": "Packaging",
        "tags": ["Denmark", "Miljøstyrelsen", "EPR"],
    },
    {
        "url": "https://www.umweltbundesamt.de/rss/presse.xml",
        "country_code": "DE",
        "category": "Packaging",
        "tags": ["Germany", "UBA", "EPR"],
    },
]

EPR_KEYWORDS = {
    "packaging", "verpackung", "förpackning", "emballage", "pakkaus",
    "producer responsibility", "erweiterte herstellerverantwortung",
    "epr", "waste", "abfall", "avfall", "jäte",
    "battery", "batteries", "batterie", "electronics", "elektro",
    "textile", "textil", "tyre", "reifen",
    "ppwr", "sup", "single-use",
}


def _is_epr_relevant(item: RegulationItem) -> bool:
    text = (item["title"] + " " + item["summary"]).lower()
    return any(kw in text for kw in EPR_KEYWORDS)


# ---------------------------------------------------------------------------
# Rate staleness check
# ---------------------------------------------------------------------------

async def _check_rate_staleness(session: AsyncSession) -> None:
    """Warn if EPR rates for any active country haven't been updated recently.

    Creates a RegulationEntry tagged 'stale-rates' so it surfaces in the UI
    and reminds the admin to verify rates with PROs before next billing cycle.
    """
    from uusio.models.obligation import EPRRate

    today = date.today()
    stale_cutoff = today - timedelta(days=RATE_STALE_DAYS)

    # Find the most recent valid_from per country+category
    from sqlalchemy import func
    rows = (await session.execute(
        select(EPRRate.country_code, EPRRate.product_category,
               func.max(EPRRate.valid_from).label("latest"))
        .where(EPRRate.valid_to.is_(None))  # currently active rates
        .group_by(EPRRate.country_code, EPRRate.product_category)
    )).all()

    for row in rows:
        if row.latest and row.latest < stale_cutoff:
            age_days = (today - row.latest).days
            tag_key = f"stale-rates-{row.country_code}-{row.product_category}"

            existing = (await session.execute(
                select(RegulationEntry).where(
                    RegulationEntry.country_code == row.country_code,
                    RegulationEntry.category == row.product_category,
                    RegulationEntry.tags.contains(["stale-rates"]),
                    RegulationEntry.is_active == True,  # noqa: E712
                )
            )).scalar_one_or_none()

            if existing is None:
                entry = RegulationEntry(
                    country_code=row.country_code,
                    category=row.product_category,
                    title=f"⚠️ EPR rates may be outdated: {row.country_code} / {row.product_category}",
                    summary=(
                        f"The EPR rates for {row.country_code} ({row.product_category}) "
                        f"were last updated {age_days} days ago (valid_from: {row.latest}). "
                        f"PROs typically update rates annually. Please verify current rates "
                        f"with the PRO and update via /api/v1/regulations if needed."
                    ),
                    source_url=None,
                    tags=["stale-rates", "action-required"],
                    effective_date=None,
                    is_active=True,
                )
                session.add(entry)
                logger.warning(
                    "regulation_monitor: rates stale for %s/%s (last updated %s, %d days ago)",
                    row.country_code, row.product_category, row.latest, age_days,
                )


# ---------------------------------------------------------------------------
# Gap analysis
# ---------------------------------------------------------------------------

async def _run_gap_analysis(session: AsyncSession) -> None:
    """Find country+category combos with active PRO contracts but no regulation entry.

    For each gap found, inserts a placeholder RegulationEntry tagged 'gap' and 'urgent'
    so it surfaces immediately in the UI as something needing attention.
    """
    # All active PRO registrations with their PRO org info
    rows = (await session.execute(
        select(CustomerPRORegistration, PROOrganisation)
        .join(PROOrganisation, CustomerPRORegistration.pro_id == PROOrganisation.id)
        .where(CustomerPRORegistration.status == "active")
    )).all()

    # Collect unique (country_code, category) pairs from active contracts
    covered_combos: set[tuple[str, str]] = set()
    for reg, pro in rows:
        categories = reg.material_categories or [pro.category]
        for cat in categories:
            covered_combos.add((pro.country_code.upper(), cat))

    if not covered_combos:
        return

    # Find which combos already have at least one active regulation entry
    existing = (await session.execute(
        select(RegulationEntry.country_code, RegulationEntry.category)
        .where(RegulationEntry.is_active == True)  # noqa: E712
    )).all()
    existing_combos = {(r.country_code.upper(), r.category) for r in existing}

    gaps = covered_combos - existing_combos
    if not gaps:
        logger.info("regulation_monitor: gap analysis — no gaps found")
        return

    logger.warning("regulation_monitor: gap analysis — %d uncovered combo(s): %s", len(gaps), gaps)

    for country_code, category in gaps:
        # Check if we already have a gap placeholder for this combo
        existing_gap = (await session.execute(
            select(RegulationEntry).where(
                RegulationEntry.country_code == country_code,
                RegulationEntry.category == category,
                RegulationEntry.tags.contains(["gap"]),
            )
        )).scalar_one_or_none()

        if existing_gap is None:
            entry = RegulationEntry(
                country_code=country_code,
                category=category,
                title=f"⚠️ Missing regulation coverage: {country_code} / {category}",
                summary=(
                    f"Your organisation has an active PRO contract in {country_code} for {category}, "
                    f"but no regulation entry exists in the library for this combination. "
                    f"Please review and add the applicable EPR regulation manually."
                ),
                source_url=None,
                tags=["gap", "urgent", "action-required"],
                effective_date=None,
                is_active=True,
            )
            session.add(entry)
            logger.info("regulation_monitor: created gap placeholder for %s/%s", country_code, category)


# ---------------------------------------------------------------------------
# Main job
# ---------------------------------------------------------------------------

async def fetch_regulation_updates(session_factory: async_sessionmaker[AsyncSession]) -> None:
    """Fetch EPR regulation updates from all sources and upsert into DB."""
    logger.info("regulation_monitor: starting weekly fetch")
    fetched: list[RegulationItem] = []

    async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
        for source in SOURCES:
            try:
                resp = await client.get(source["url"])
                resp.raise_for_status()
                items = _parse_rss(
                    resp.text,
                    source["country_code"],
                    source["category"],
                    source["tags"],
                )
                relevant = [_tag_urgency(i) for i in items if _is_epr_relevant(i)]
                logger.info(
                    "regulation_monitor: %s → %d items, %d EPR-relevant (%d urgent)",
                    source["url"],
                    len(items),
                    len(relevant),
                    sum(1 for i in relevant if "urgent" in i["tags"]),
                )
                fetched.extend(relevant)
            except Exception as exc:
                logger.warning("regulation_monitor: failed to fetch %s: %s", source["url"], exc)

    async with session_factory() as session:
        new_count = 0
        urgent_count = 0

        for item in fetched:
            existing = None
            if item.get("source_url"):
                existing = (await session.execute(
                    select(RegulationEntry).where(RegulationEntry.source_url == item["source_url"])
                )).scalar_one_or_none()

            if existing is None:
                entry = RegulationEntry(
                    country_code=item["country_code"],
                    category=item["category"],
                    title=item["title"],
                    summary=item["summary"],
                    source_url=item.get("source_url"),
                    tags=item["tags"],
                    effective_date=item.get("effective_date"),
                    is_active=True,
                )
                session.add(entry)
                new_count += 1
                if "urgent" in item["tags"]:
                    urgent_count += 1
            else:
                # Update urgency tag on existing entry if it has become urgent
                if "urgent" in item["tags"] and "urgent" not in (existing.tags or []):
                    existing.tags = list(existing.tags or []) + ["urgent"]

        await _run_gap_analysis(session)
        await _check_rate_staleness(session)
        await session.commit()

        logger.info(
            "regulation_monitor: inserted %d new entries (%d urgent), gap analysis complete",
            new_count, urgent_count,
        )
