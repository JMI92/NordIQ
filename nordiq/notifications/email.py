"""Email notification service using aiosmtplib.

Sends deadline warning emails to all active users of a customer.
All methods are async-safe and designed to be called from the APScheduler
AsyncIOScheduler running inside the FastAPI event loop.

SMTP credentials are read from Settings at call time (not at import time) so
that tests can override them via env vars.
"""

from __future__ import annotations

import logging
from email.message import EmailMessage

import aiosmtplib

from nordiq.core.config import get_settings

logger = logging.getLogger(__name__)


async def send_deadline_warning(
    recipient_email: str,
    recipient_name: str,
    customer_name: str,
    country_code: str,
    product_category: str,
    reporting_period_start: str,
    reporting_period_end: str,
    submission_deadline: str,
    days_remaining: int,
    pro_id: str,
) -> bool:
    """Send a deadline warning email.

    Returns True on success, False on any SMTP error (errors are logged but
    never re-raised so that one bad recipient doesn't abort the batch).
    """
    settings = get_settings()

    subject = (
        f"[UUSIO] ⚠️ EPR deadline in {days_remaining} day(s) — "
        f"{country_code} {product_category} due {submission_deadline}"
    )

    body = _build_body(
        recipient_name=recipient_name,
        customer_name=customer_name,
        country_code=country_code,
        product_category=product_category,
        reporting_period_start=reporting_period_start,
        reporting_period_end=reporting_period_end,
        submission_deadline=submission_deadline,
        days_remaining=days_remaining,
        pro_id=pro_id,
    )

    if settings.use_ses:
        from nordiq.notifications.ses import send_via_ses
        return await send_via_ses(
            recipient_email=recipient_email,
            subject=subject,
            body_text=body,
            body_html=_build_html_body(body, subject),
        )

    msg = EmailMessage()
    msg["From"] = settings.smtp_from
    msg["To"] = recipient_email
    msg["Subject"] = subject
    msg.set_content(body)
    msg.add_alternative(_build_html_body(body, subject), subtype="html")

    try:
        await aiosmtplib.send(
            msg,
            hostname=settings.smtp_host,
            port=settings.smtp_port,
            username=settings.smtp_user or None,
            password=settings.smtp_password or None,
            use_tls=False,
            start_tls=settings.smtp_tls,
        )
        logger.info(
            "Deadline warning sent to %s (%s %s due %s, %d days remaining)",
            recipient_email, country_code, product_category, submission_deadline, days_remaining,
        )
        return True
    except Exception as exc:
        logger.error(
            "Failed to send deadline warning to %s: %s", recipient_email, exc
        )
        return False


def _build_body(
    *,
    recipient_name: str,
    customer_name: str,
    country_code: str,
    product_category: str,
    reporting_period_start: str,
    reporting_period_end: str,
    submission_deadline: str,
    days_remaining: int,
    pro_id: str,
) -> str:
    urgency = "URGENT: " if days_remaining <= 7 else ""
    return f"""{urgency}EPR Reporting Deadline Reminder

Dear {recipient_name},

This is an automated reminder from UUSIO for {customer_name}.

You have an upcoming EPR reporting deadline:

  Country:           {country_code}
  Product category:  {product_category}
  Reporting period:  {reporting_period_start} to {reporting_period_end}
  PRO organisation:  {pro_id}
  Submission due:    {submission_deadline}
  Days remaining:    {days_remaining}

Please log in to UUSIO to run or review your calculation and submit your report
before the deadline.

If you have already submitted this report, you can ignore this reminder.

---
This email was sent automatically by UUSIO EPR Compliance.
To stop receiving these notifications, contact your account administrator.
"""


def _build_html_body(plain_text: str, subject: str) -> str:
    safe = plain_text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    lines = safe.split("\n")
    html_lines = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            html_lines.append("<br>")
        elif stripped.startswith("Dear ") or stripped.startswith("This is"):
            html_lines.append(f"<p>{line}</p>")
        else:
            html_lines.append(f"<p style='margin:2px 0'>{line}</p>")
    body_html = "\n".join(html_lines)
    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"></head>
<body style="font-family:sans-serif;max-width:600px;margin:auto;padding:20px">
<h2 style="color:#d97706">{subject}</h2>
{body_html}
</body></html>"""
