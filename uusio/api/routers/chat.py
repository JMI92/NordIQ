"""AI chat assistant — two modes.

public:  Sales bot for the marketing site. No auth required.
         Answers questions about Uusio, pricing, supported countries.
         Directs interested visitors to book a demo.

portal:  Compliance assistant for logged-in customers.
         Has access to the customer's own obligations, deadlines,
         submissions and invoices. Answers questions about their
         specific EPR situation.
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Annotated

import anthropic
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from uusio.api.dependencies import get_current_user, get_db
from uusio.core.config import get_settings
from uusio.models.user import User

logger = logging.getLogger(__name__)
router = APIRouter()

MODEL = "claude-sonnet-4-6"
MAX_TOKENS = 1024

# ---------------------------------------------------------------------------
# System prompts
# ---------------------------------------------------------------------------

PUBLIC_SYSTEM_PROMPT = """You are Uusio's AI assistant on the Uusio marketing website.

Uusio is a SaaS platform that automates European EPR (Extended Producer Responsibility) compliance for manufacturers, hardware companies and e-commerce businesses selling physical products in Europe.

KEY FACTS:
- EPR requires companies placing products on the European market to register with PRO organisations (Producer Responsibility Organisations) in each country and pay material fees based on packaging weight
- Uusio handles everything: PRO registrations, fee calculations, report generation and submission, deadline tracking
- Single point of contact — instead of managing 18+ different PRO portals, customers have one login

SUPPORTED MARKETS AND WASTE STREAMS:
- Nordic countries (Finland, Sweden, Norway, Denmark): packaging, WEEE, batteries
- Core Europe (Germany, France, Italy, Austria, Belgium, Netherlands, Spain, Portugal, Ireland, Estonia): packaging, batteries, WEEE
- Full Europe: all of the above + Switzerland, UK

PRICING (monthly subscription + setup):
- Nordics: €990/month
- Core Europe: €2,490/month
- Full Europe: €3,990/month
- Setup fees apply (one-time onboarding)
- Material fee margin: 15% on top of PRO rates (annual and registration fees passed through at cost)

HOW IT WORKS:
1. Customer onboards — enters products and packaging data
2. Uusio calculates EPR obligations per country and waste stream
3. Reports are automatically submitted to PROs by email
4. Customer receives one consolidated invoice per month

YOUR ROLE:
- Answer questions about EPR compliance, Uusio's features and pricing
- Help visitors understand if Uusio is right for them
- If someone wants a demo or is ready to start: direct them to contact@uusio.io
- Keep answers concise and professional
- Do not invent features or pricing that aren't listed above
- If you don't know something, say so and suggest they email contact@uusio.io

Always respond in the same language the visitor uses."""


PORTAL_SYSTEM_PROMPT_TEMPLATE = """You are Uusio's compliance assistant for {customer_name}.

You help this customer understand their EPR compliance status, upcoming deadlines, obligations and invoices.

TODAY'S DATE: {today}

CUSTOMER CONTEXT:
{customer_context}

YOUR ROLE:
- Answer questions about the customer's specific EPR obligations and deadlines
- Explain what actions are needed and when
- Help interpret their calculation results and invoices
- If something requires manual action from Uusio staff, say so clearly
- Be concise and practical — these are busy compliance managers

Always respond in the same language the customer uses."""


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------

class ChatMessage(BaseModel):
    role: str   # "user" or "assistant"
    content: str


class ChatRequest(BaseModel):
    message: str
    mode: str = "public"   # "public" or "portal"
    history: list[ChatMessage] = []


class ChatResponse(BaseModel):
    reply: str
    mode: str


# ---------------------------------------------------------------------------
# Context builder for portal mode
# ---------------------------------------------------------------------------

async def _build_customer_context(customer_id, db: AsyncSession) -> str:
    from uusio.models.billing import Invoice
    from uusio.models.obligation import EPRObligation, ReportingDeadline
    from uusio.models.pro_registry import CustomerPRORegistration, PROOrganisation
    from uusio.models.submission import PROSubmission

    today = date.today()

    # Active PRO registrations
    regs = (await db.execute(
        select(CustomerPRORegistration, PROOrganisation)
        .join(PROOrganisation, CustomerPRORegistration.pro_id == PROOrganisation.id)
        .where(CustomerPRORegistration.customer_id == customer_id,
               CustomerPRORegistration.status == "active")
    )).all()

    # Upcoming deadlines (next 90 days)
    deadlines = (await db.execute(
        select(ReportingDeadline).where(
            ReportingDeadline.submission_deadline >= today,
        ).order_by(ReportingDeadline.submission_deadline).limit(10)
    )).scalars().all()

    # Recent obligations
    obligations = (await db.execute(
        select(EPRObligation).where(
            EPRObligation.customer_id == customer_id,
        ).order_by(EPRObligation.reporting_period_start.desc()).limit(20)
    )).scalars().all()

    # Unpaid invoices
    invoices = (await db.execute(
        select(Invoice).where(
            Invoice.customer_id == customer_id,
            Invoice.status.in_(["draft", "sent", "overdue"]),
        ).order_by(Invoice.due_date).limit(10)
    )).scalars().all()

    # Recent submissions
    submissions = (await db.execute(
        select(PROSubmission).where(
            PROSubmission.customer_id == customer_id,
        ).order_by(PROSubmission.created_at.desc()).limit(10)
    )).scalars().all()

    lines = []

    if regs:
        lines.append("ACTIVE PRO REGISTRATIONS:")
        for reg, pro in regs:
            lines.append(f"  - {pro.name} ({pro.country_code}) — {', '.join(reg.material_categories or [pro.category])}")

    if deadlines:
        lines.append("\nUPCOMING DEADLINES:")
        for d in deadlines:
            days_left = (d.submission_deadline - today).days
            lines.append(f"  - {d.country_code} {d.product_category}: due {d.submission_deadline.isoformat()} ({days_left} days)")

    if obligations:
        lines.append("\nRECENT OBLIGATIONS:")
        for o in obligations:
            lines.append(
                f"  - {o.country_code} {o.product_category} "
                f"{o.reporting_period_start} – {o.reporting_period_end}: "
                f"status={o.status}, fee={o.fee_amount} {o.currency}"
            )

    if invoices:
        lines.append("\nOPEN INVOICES:")
        for inv in invoices:
            lines.append(
                f"  - {inv.invoice_number} ({inv.invoice_type}): "
                f"{float(inv.amount):.2f} {inv.currency}, due {inv.due_date}, status={inv.status}"
            )

    if submissions:
        lines.append("\nRECENT SUBMISSIONS:")
        for s in submissions:
            lines.append(f"  - obligation {s.obligation_id}: method={s.submission_method}, status={s.status}")

    if not lines:
        return "No data available yet — customer is newly onboarded."

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/public", response_model=ChatResponse)
async def public_chat(body: ChatRequest):
    """Public sales bot — no authentication required."""
    settings = get_settings()
    if not settings.anthropic_api_key:
        raise HTTPException(status_code=503, detail="AI assistant not configured")

    client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)

    messages = [{"role": m.role, "content": m.content} for m in body.history]
    messages.append({"role": "user", "content": body.message})

    try:
        response = await client.messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            system=PUBLIC_SYSTEM_PROMPT,
            messages=messages,
        )
        reply = response.content[0].text
    except Exception as exc:
        logger.error("Public chat error: %s", exc)
        raise HTTPException(status_code=502, detail="AI assistant unavailable")

    return ChatResponse(reply=reply, mode="public")


@router.post("/portal", response_model=ChatResponse)
async def portal_chat(
    body: ChatRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Portal compliance assistant — requires authentication."""
    from uusio.models.customer import Customer

    settings = get_settings()
    if not settings.anthropic_api_key:
        raise HTTPException(status_code=503, detail="AI assistant not configured")

    customer = (await db.execute(
        select(Customer).where(Customer.id == current_user.customer_id)
    )).scalar_one_or_none()
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")

    customer_context = await _build_customer_context(current_user.customer_id, db)

    system_prompt = PORTAL_SYSTEM_PROMPT_TEMPLATE.format(
        customer_name=customer.name,
        today=date.today().isoformat(),
        customer_context=customer_context,
    )

    client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)

    messages = [{"role": m.role, "content": m.content} for m in body.history]
    messages.append({"role": "user", "content": body.message})

    try:
        response = await client.messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            system=system_prompt,
            messages=messages,
        )
        reply = response.content[0].text
    except Exception as exc:
        logger.error("Portal chat error for customer %s: %s", customer.id, exc)
        raise HTTPException(status_code=502, detail="AI assistant unavailable")

    return ChatResponse(reply=reply, mode="portal")
