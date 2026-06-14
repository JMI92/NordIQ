"""AWS SES email sending via boto3."""
from __future__ import annotations
import logging
from nordiq.core.config import get_settings

logger = logging.getLogger(__name__)


async def send_via_ses(
    recipient_email: str,
    subject: str,
    body_text: str,
    body_html: str,
) -> bool:
    """Send email via AWS SES. Returns True on success."""
    import boto3
    s = get_settings()
    sender = s.ses_from or s.smtp_from
    kwargs = {"region_name": s.aws_region}
    if s.aws_access_key_id:
        kwargs["aws_access_key_id"] = s.aws_access_key_id
        kwargs["aws_secret_access_key"] = s.aws_secret_access_key
    client = boto3.client("ses", **kwargs)
    try:
        client.send_email(
            Source=sender,
            Destination={"ToAddresses": [recipient_email]},
            Message={
                "Subject": {"Data": subject, "Charset": "UTF-8"},
                "Body": {
                    "Text": {"Data": body_text, "Charset": "UTF-8"},
                    "Html": {"Data": body_html, "Charset": "UTF-8"},
                },
            },
        )
        logger.info("SES email sent to %s", recipient_email)
        return True
    except Exception as exc:
        logger.error("SES send failed to %s: %s", recipient_email, exc)
        return False
