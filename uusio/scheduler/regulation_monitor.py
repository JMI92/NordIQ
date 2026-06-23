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
"""

from __future__ import annotations

import hashlib
import logging
import re
from datetime import date, datetime
from typing import TypedDict
from xml.etree import ElementTree

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from uusio.models.regulation import RegulationEntry

logger = logging.getLogger(__name__)


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
            tags=tags,
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
            tags=tags,
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


# ---------------------------------------------------------------------------
# Feed sources
# ---------------------------------------------------------------------------

SOURCES = [
    # EUR-Lex: environment/waste legislation feed
    {
        "url": "https://eur-lex.europa.eu/rss/rss-notifications.xml?language=EN&subject=environmental_legislation",
        "country_code": "EU",
        "category": "Packaging",
        "tags": ["EUR-Lex", "EU", "EPR"],
    },
    # EUR-Lex: packaging and packaging waste
    {
        "url": "https://eur-lex.europa.eu/search.html?type=quick&lang=en&term=packaging+producer+responsibility&format=rss",
        "country_code": "EU",
        "category": "Packaging",
        "tags": ["EUR-Lex", "PPWR", "packaging"],
    },
    # Swedish EPA news
    {
        "url": "https://www.naturvardsverket.se/rss/nyheter.xml",
        "country_code": "SE",
        "category": "Packaging",
        "tags": ["Sweden", "Naturvårdsverket", "EPR"],
    },
    # Finnish SYKE news
    {
        "url": "https://www.syke.fi/fi-FI/Rss/Uutiset",
        "country_code": "FI",
        "category": "Packaging",
        "tags": ["Finland", "SYKE", "EPR"],
    },
    # Norwegian Environment Agency
    {
        "url": "https://www.miljodirektoratet.no/rss/nyheter/",
        "country_code": "NO",
        "category": "Packaging",
        "tags": ["Norway", "Miljødirektoratet", "EPR"],
    },
    # Danish EPA
    {
        "url": "https://mst.dk/service/nyheder/nyhedsarkiv/rss/",
        "country_code": "DK",
        "category": "Packaging",
        "tags": ["Denmark", "Miljøstyrelsen", "EPR"],
    },
    # German UBA news
    {
        "url": "https://www.umweltbundesamt.de/rss/presse.xml",
        "country_code": "DE",
        "category": "Packaging",
        "tags": ["Germany", "UBA", "EPR"],
    },
]

# Keywords that indicate EPR relevance — items without any of these are skipped
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


def _stable_key(item: RegulationItem) -> str:
    """Deterministic dedup key based on URL or title+country."""
    raw = item.get("source_url") or f"{item['country_code']}:{item['title']}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


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
                relevant = [i for i in items if _is_epr_relevant(i)]
                logger.info(
                    "regulation_monitor: %s → %d items, %d EPR-relevant",
                    source["url"], len(items), len(relevant),
                )
                fetched.extend(relevant)
            except Exception as exc:
                logger.warning("regulation_monitor: failed to fetch %s: %s", source["url"], exc)

    if not fetched:
        logger.info("regulation_monitor: no new items found")
        return

    async with session_factory() as session:
        new_count = 0
        for item in fetched:
            key = _stable_key(item)
            # Check by source_url to avoid duplicates
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

        await session.commit()
        logger.info("regulation_monitor: inserted %d new regulation entries", new_count)
