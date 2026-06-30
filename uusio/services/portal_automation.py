"""PRO portal submission automation.

For PROs whose only reporting channel is a web portal (no API), we drive
a headless browser (Playwright) through login + report submission. This
module defines the adapter contract and the orchestration/retry/alerting
loop that every adapter runs inside — individual adapters (one per portal)
live in uusio/services/portal_adapters/ and register themselves below.

Design notes (see PRO portal automation architecture discussion):
  - Credentials are never read by application code directly; only this
    orchestrator decrypts them, for the duration of one submission run.
  - A submission is only marked SUCCESS after verify_submission() confirms
    a reference/receipt on the portal — a "looks like it worked" login
    is not sufficient.
"""

import logging
from datetime import datetime, timezone
from typing import Protocol

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from uusio.core.security import decrypt_config
from uusio.models.customer import Customer
from uusio.models.obligation import EPRObligation
from uusio.models.pro_registry import CustomerPRORegistration, PROOrganisation, PROPortalCredential
from uusio.models.submission import PROSubmission
from uusio.services.alerting import alert_submission_failure

logger = logging.getLogger(__name__)

MAX_ATTEMPTS = 3


class PortalCredentials:
    def __init__(self, username: str, password: str, portal_url: str | None):
        self.username = username
        self.password = password
        self.portal_url = portal_url


class SubmissionResult:
    def __init__(self, ok: bool, reference: str | None = None, error: str | None = None, screenshot: bytes | None = None):
        self.ok = ok
        self.reference = reference
        self.error = error
        self.screenshot = screenshot


class PortalAdapter(Protocol):
    """One implementation per PRO portal. Lives under portal_adapters/<pro_key>.py."""

    async def login(self, creds: PortalCredentials) -> SubmissionResult: ...

    async def submit_report(self, creds: PortalCredentials, obligation: EPRObligation) -> SubmissionResult: ...

    async def verify_submission(self, creds: PortalCredentials, reference: str) -> bool: ...


# Populated by portal_adapters/__init__.py as adapters are built — one entry
# per PROOrganisation.pro_key that uses submission_method == "portal".
ADAPTER_REGISTRY: dict[str, PortalAdapter] = {}


async def run_submission(
    db: AsyncSession,
    registration: CustomerPRORegistration,
    pro: PROOrganisation,
    customer: Customer,
    obligation: EPRObligation,
) -> PROSubmission:
    """Run (or retry) a portal submission for one obligation. Always returns
    a PROSubmission row — callers should commit afterwards.
    """
    submission = PROSubmission(
        customer_id=customer.id,
        obligation_id=obligation.id,
        pro_id=pro.pro_key,
        submission_method="portal",
    )
    db.add(submission)

    adapter = ADAPTER_REGISTRY.get(pro.pro_key)
    if adapter is None:
        submission.status = "failed"
        submission.error_message = f"No portal adapter registered for pro_key={pro.pro_key!r}"
        submission.needs_attention = True
        await _alert(submission, customer, pro)
        return submission

    cred_row = (
        await db.execute(
            select(PROPortalCredential).where(
                PROPortalCredential.customer_pro_registration_id == registration.id
            )
        )
    ).scalar_one_or_none()
    if cred_row is None or cred_row.status != "active":
        submission.status = "failed"
        submission.error_message = "No active portal credentials stored for this registration"
        submission.needs_attention = True
        await _alert(submission, customer, pro)
        return submission

    secret = decrypt_config(cred_row.password_encrypted)
    creds = PortalCredentials(cred_row.username, secret["password"], cred_row.portal_url)

    last_error = "unknown error"
    for attempt in range(1, MAX_ATTEMPTS + 1):
        submission.retry_count = attempt - 1
        try:
            login_result = await adapter.login(creds)
            if not login_result.ok:
                cred_row.status = "invalid"
                last_error = f"login failed: {login_result.error}"
                if login_result.screenshot:
                    submission.screenshot_s3_key = _store_screenshot(submission, login_result.screenshot)
                break  # bad credentials won't succeed on retry — stop immediately

            cred_row.last_verified_at = datetime.now(timezone.utc)

            submit_result = await adapter.submit_report(creds, obligation)
            if not submit_result.ok:
                last_error = f"submit failed: {submit_result.error}"
                if submit_result.screenshot:
                    submission.screenshot_s3_key = _store_screenshot(submission, submit_result.screenshot)
                continue  # transient — retry

            verified = await adapter.verify_submission(creds, submit_result.reference or "")
            if not verified:
                last_error = "submission sent but could not be verified on the portal"
                submission.status = "pending"
                submission.error_message = last_error
                submission.needs_attention = True
                await _alert(submission, customer, pro)
                return submission

            submission.status = "success"
            submission.response_payload = {"reference": submit_result.reference}
            return submission

        except Exception as exc:  # noqa: BLE001 — any adapter failure must not crash the worker
            logger.exception("Portal automation attempt %s/%s failed for %s", attempt, MAX_ATTEMPTS, pro.pro_key)
            last_error = str(exc)

    submission.status = "failed"
    submission.error_message = last_error
    submission.needs_attention = True
    await _alert(submission, customer, pro)
    return submission


def _store_screenshot(submission: PROSubmission, screenshot: bytes) -> str:
    from uusio.storage.s3 import upload_bytes

    key = f"submission-debug/{submission.customer_id}/{submission.id}.png"
    upload_bytes(screenshot, key, content_type="image/png")
    return key


async def _alert(submission: PROSubmission, customer: Customer, pro: PROOrganisation) -> None:
    await alert_submission_failure(
        customer_name=customer.name,
        pro_name=pro.name,
        obligation_id=str(submission.obligation_id),
        error_message=submission.error_message or "unknown error",
        screenshot_s3_key=submission.screenshot_s3_key,
    )
