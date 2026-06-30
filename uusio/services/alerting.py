"""Admin alerts for portal automation failures.

Sends an email via the existing SES helper to settings.admin_alert_email
whenever a portal submission run exhausts its retries. If no alert
address is configured, the failure is still logged so it isn't silent.
"""

import logging

from uusio.core.config import get_settings
from uusio.notifications.ses import send_via_ses

logger = logging.getLogger(__name__)


async def alert_submission_failure(
    *,
    customer_name: str,
    pro_name: str,
    obligation_id: str,
    error_message: str,
    screenshot_s3_key: str | None = None,
) -> None:
    """Notify admins that a portal submission needs manual attention."""
    settings = get_settings()
    subject = f"[Uusio] Submission failed: {customer_name} → {pro_name}"
    lines = [
        f"Customer: {customer_name}",
        f"PRO: {pro_name}",
        f"Obligation: {obligation_id}",
        f"Error: {error_message}",
    ]
    if screenshot_s3_key:
        lines.append(f"Screenshot: s3://{settings.s3_bucket}/{screenshot_s3_key}")
    body_text = "\n".join(lines)
    body_html = "<br>".join(lines)

    if not settings.admin_alert_email:
        logger.error("Portal submission needs attention (no admin_alert_email configured): %s", body_text)
        return

    sent = await send_via_ses(settings.admin_alert_email, subject, body_text, body_html)
    if not sent:
        logger.error("Failed to send submission-failure alert email: %s", body_text)
