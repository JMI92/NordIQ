"""Unit tests for the deadline checker and email notification logic.

All DB calls are mocked — no Postgres required.
All SMTP calls are mocked — no mail server required.
"""

from __future__ import annotations

import asyncio
from datetime import date, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from nordiq.scheduler.deadline_checker import (
    WARNING_THRESHOLDS,
    _customer_has_submitted,
    _load_deadlines,
    _notify_customers_for_deadline,
    _send_warnings_to_customer_users,
    check_upcoming_deadlines,
)


def _make_deadline(days_from_now: int, country: str = "FI", category: str = "packaging"):
    d = MagicMock()
    d.submission_deadline = date.today() + timedelta(days=days_from_now)
    d.country_code = country
    d.product_category = category
    d.reporting_period_start = date(2024, 1, 1)
    d.reporting_period_end = date(2024, 12, 31)
    d.pro_id = f"nordic_pro_{country.lower()}"
    return d


def _make_customer(name: str = "Acme Oy"):
    c = MagicMock()
    c.id = "cust-uuid-1"
    c.name = name
    c.is_active = True
    return c


def _make_user(email: str = "user@acme.fi", full_name: str = "Test User"):
    u = MagicMock()
    u.email = email
    u.full_name = full_name
    u.customer_id = "cust-uuid-1"
    u.is_active = True
    return u


def _async_scalar_result(items):
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = items
    mock_scalars.scalar_one_or_none = MagicMock(return_value=items[0] if items else None)
    mock_result = MagicMock()
    mock_result.scalars.return_value = mock_scalars
    mock_result.scalar_one_or_none = MagicMock(return_value=items[0] if items else None)
    return mock_result


def _make_session_factory(db: AsyncMock) -> MagicMock:
    ctx = MagicMock()
    ctx.__aenter__ = AsyncMock(return_value=db)
    ctx.__aexit__ = AsyncMock(return_value=False)
    factory = MagicMock(return_value=ctx)
    return factory


def test_warning_thresholds_are_correct():
    assert set(WARNING_THRESHOLDS) == {30, 14, 7, 1}


def test_warning_thresholds_are_sorted_descending():
    assert list(WARNING_THRESHOLDS) == sorted(WARNING_THRESHOLDS, reverse=True)


@pytest.mark.asyncio
async def test_load_deadlines_returns_list():
    db = AsyncMock()
    deadlines = [_make_deadline(7), _make_deadline(14)]
    db.execute.return_value = _async_scalar_result(deadlines)
    result = await _load_deadlines(db, date.today())
    assert len(result) == 2


@pytest.mark.asyncio
async def test_load_deadlines_empty_when_none():
    db = AsyncMock()
    db.execute.return_value = _async_scalar_result([])
    result = await _load_deadlines(db, date.today())
    assert result == []


@pytest.mark.asyncio
async def test_customer_has_submitted_true_when_submitted():
    db = AsyncMock()
    obligation = MagicMock()
    db.execute.return_value = _async_scalar_result([obligation])
    deadline = _make_deadline(7)
    result = await _customer_has_submitted(db, "cust-1", deadline)
    assert result is True


@pytest.mark.asyncio
async def test_customer_has_submitted_false_when_none():
    db = AsyncMock()
    db.execute.return_value = _async_scalar_result([])
    deadline = _make_deadline(7)
    result = await _customer_has_submitted(db, "cust-1", deadline)
    assert result is False


@pytest.mark.asyncio
async def test_send_warnings_calls_email_for_each_user():
    db = AsyncMock()
    users = [_make_user("a@test.fi"), _make_user("b@test.fi")]
    db.execute.return_value = _async_scalar_result(users)
    customer = _make_customer()
    deadline = _make_deadline(7)
    with patch(
        "nordiq.scheduler.deadline_checker.send_deadline_warning",
        new_callable=AsyncMock, return_value=True,
    ) as mock_send:
        await _send_warnings_to_customer_users(db, customer, deadline, 7)
    assert mock_send.call_count == 2
    emails_sent = {call.kwargs["recipient_email"] for call in mock_send.call_args_list}
    assert emails_sent == {"a@test.fi", "b@test.fi"}


@pytest.mark.asyncio
async def test_send_warnings_no_users_sends_nothing():
    db = AsyncMock()
    db.execute.return_value = _async_scalar_result([])
    customer = _make_customer()
    deadline = _make_deadline(7)
    with patch(
        "nordiq.scheduler.deadline_checker.send_deadline_warning",
        new_callable=AsyncMock,
    ) as mock_send:
        await _send_warnings_to_customer_users(db, customer, deadline, 7)
    mock_send.assert_not_called()


@pytest.mark.asyncio
async def test_send_warnings_passes_correct_args():
    db = AsyncMock()
    user = _make_user("cfo@acme.fi", "CFO Person")
    db.execute.return_value = _async_scalar_result([user])
    customer = _make_customer("Acme Oy")
    deadline = _make_deadline(14, country="SE", category="packaging")
    with patch(
        "nordiq.scheduler.deadline_checker.send_deadline_warning",
        new_callable=AsyncMock, return_value=True,
    ) as mock_send:
        await _send_warnings_to_customer_users(db, customer, deadline, 14)
    call_kwargs = mock_send.call_args.kwargs
    assert call_kwargs["recipient_email"] == "cfo@acme.fi"
    assert call_kwargs["recipient_name"] == "CFO Person"
    assert call_kwargs["customer_name"] == "Acme Oy"
    assert call_kwargs["country_code"] == "SE"
    assert call_kwargs["days_remaining"] == 14


@pytest.mark.asyncio
async def test_notify_skips_already_submitted_customers():
    db = AsyncMock()
    customer = _make_customer()
    deadline = _make_deadline(7)
    customers_result = _async_scalar_result([customer])
    submitted_result = _async_scalar_result([MagicMock()])
    db.execute.side_effect = [customers_result, submitted_result]
    with patch(
        "nordiq.scheduler.deadline_checker.send_deadline_warning",
        new_callable=AsyncMock,
    ) as mock_send:
        await _notify_customers_for_deadline(db, deadline, 7)
    mock_send.assert_not_called()


@pytest.mark.asyncio
async def test_notify_sends_for_unsubmitted_customers():
    db = AsyncMock()
    customer = _make_customer()
    user = _make_user()
    deadline = _make_deadline(7)
    db.execute.side_effect = [
        _async_scalar_result([customer]),
        _async_scalar_result([]),   # not submitted
        _async_scalar_result([user]),
    ]
    with patch(
        "nordiq.scheduler.deadline_checker.send_deadline_warning",
        new_callable=AsyncMock, return_value=True,
    ) as mock_send:
        await _notify_customers_for_deadline(db, deadline, 7)
    mock_send.assert_called_once()


@pytest.mark.asyncio
async def test_check_upcoming_deadlines_skips_non_threshold_days():
    db = AsyncMock()
    deadline = _make_deadline(10)  # 10 not in {30, 14, 7, 1}
    db.execute.return_value = _async_scalar_result([deadline])
    with patch(
        "nordiq.scheduler.deadline_checker.send_deadline_warning",
        new_callable=AsyncMock,
    ) as mock_send:
        await check_upcoming_deadlines(_make_session_factory(db))
    mock_send.assert_not_called()


@pytest.mark.asyncio
async def test_check_upcoming_deadlines_fires_at_threshold():
    db = AsyncMock()
    deadline = _make_deadline(7)
    customer = _make_customer()
    user = _make_user()
    db.execute.side_effect = [
        _async_scalar_result([deadline]),
        _async_scalar_result([customer]),
        _async_scalar_result([]),   # not submitted
        _async_scalar_result([user]),
    ]
    with patch(
        "nordiq.scheduler.deadline_checker.send_deadline_warning",
        new_callable=AsyncMock, return_value=True,
    ) as mock_send:
        await check_upcoming_deadlines(_make_session_factory(db))
    mock_send.assert_called_once()


@pytest.mark.asyncio
async def test_check_upcoming_deadlines_no_deadlines():
    db = AsyncMock()
    db.execute.return_value = _async_scalar_result([])
    with patch(
        "nordiq.scheduler.deadline_checker.send_deadline_warning",
        new_callable=AsyncMock,
    ) as mock_send:
        await check_upcoming_deadlines(_make_session_factory(db))
    mock_send.assert_not_called()


def test_email_body_content():
    from nordiq.notifications.email import _build_body
    body = _build_body(
        recipient_name="Juho", customer_name="Acme Oy", country_code="FI",
        product_category="packaging", reporting_period_start="2024-01-01",
        reporting_period_end="2024-12-31", submission_deadline="2025-01-31",
        days_remaining=7, pro_id="nordic_pro_fi",
    )
    assert "Juho" in body
    assert "Acme Oy" in body
    assert "FI" in body
    assert "2025-01-31" in body
    assert "7" in body
    assert "URGENT" in body


def test_email_body_not_urgent_at_30_days():
    from nordiq.notifications.email import _build_body
    body = _build_body(
        recipient_name="Test", customer_name="Test Corp", country_code="SE",
        product_category="packaging", reporting_period_start="2024-01-01",
        reporting_period_end="2024-12-31", submission_deadline="2025-02-28",
        days_remaining=30, pro_id="nordic_pro_se",
    )
    assert "URGENT" not in body


def test_email_html_body_contains_subject():
    from nordiq.notifications.email import _build_html_body
    html = _build_html_body("plain text content", "My Subject")
    assert "My Subject" in html
    assert "<!DOCTYPE html>" in html


@pytest.mark.parametrize("days", WARNING_THRESHOLDS)
def test_warning_thresholds_urgency(days):
    from nordiq.notifications.email import _build_body
    body = _build_body(
        recipient_name="Test", customer_name="Test", country_code="FI",
        product_category="packaging", reporting_period_start="2024-01-01",
        reporting_period_end="2024-12-31", submission_deadline="2025-01-31",
        days_remaining=days, pro_id="nordic_pro_fi",
    )
    if days <= 7:
        assert "URGENT" in body
    else:
        assert "URGENT" not in body
