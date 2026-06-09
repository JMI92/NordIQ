"""Thin HTTP client for the NordIQ API.

All Streamlit pages import from here — never call requests directly in page code.
The base URL is read from st.session_state["api_url"] (set at login) or falls back
to the API_URL environment variable.
"""

from __future__ import annotations

import os
from typing import Any

import requests
import streamlit as st


def _base_url() -> str:
    return st.session_state.get("api_url") or os.getenv("API_URL", "http://localhost:8000")


def _headers() -> dict:
    token = st.session_state.get("token")
    if token:
        return {"Authorization": f"Bearer {token}"}
    return {}


def _handle(response: requests.Response) -> Any:
    if response.status_code == 401:
        st.session_state.clear()
        st.error("Session expired — please log in again.")
        st.stop()
    if not response.ok:
        detail = response.json().get("detail", response.text) if response.content else response.text
        st.error(f"API error {response.status_code}: {detail}")
        st.stop()
    if response.status_code == 204:
        return None
    return response.json()


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

def login(username: str, password: str) -> dict:
    """POST /api/v1/auth/login — returns token dict."""
    resp = requests.post(
        f"{_base_url()}/api/v1/auth/login",
        data={"username": username, "password": password},
        timeout=10,
    )
    return _handle(resp)


def health() -> dict:
    resp = requests.get(f"{_base_url()}/health", timeout=5)
    return resp.json() if resp.ok else {"status": "unreachable"}


# ---------------------------------------------------------------------------
# Data sources
# ---------------------------------------------------------------------------

def list_data_sources() -> list[dict]:
    resp = requests.get(
        f"{_base_url()}/api/v1/data-sources",
        headers=_headers(),
        timeout=10,
    )
    return _handle(resp)


def create_data_source(payload: dict) -> dict:
    resp = requests.post(
        f"{_base_url()}/api/v1/data-sources",
        json=payload,
        headers=_headers(),
        timeout=10,
    )
    return _handle(resp)


def delete_data_source(ds_id: str) -> None:
    resp = requests.delete(
        f"{_base_url()}/api/v1/data-sources/{ds_id}",
        headers=_headers(),
        timeout=10,
    )
    _handle(resp)


def test_data_source(ds_id: str) -> dict:
    resp = requests.post(
        f"{_base_url()}/api/v1/data-sources/{ds_id}/test",
        headers=_headers(),
        timeout=30,
    )
    return _handle(resp)


# ---------------------------------------------------------------------------
# Products
# ---------------------------------------------------------------------------

def list_products(limit: int = 100, offset: int = 0) -> list[dict]:
    resp = requests.get(
        f"{_base_url()}/api/v1/products",
        headers=_headers(),
        params={"limit": limit, "offset": offset},
        timeout=10,
    )
    return _handle(resp)


def list_product_weights(product_id: str) -> list[dict]:
    resp = requests.get(
        f"{_base_url()}/api/v1/products/{product_id}/weights",
        headers=_headers(),
        timeout=10,
    )
    return _handle(resp)


def upload_products_csv(file_bytes: bytes, filename: str) -> dict:
    resp = requests.post(
        f"{_base_url()}/api/v1/products/upload-csv",
        headers=_headers(),
        files={"file": (filename, file_bytes, "text/csv")},
        timeout=60,
    )
    return _handle(resp)


# ---------------------------------------------------------------------------
# Calculations
# ---------------------------------------------------------------------------

def run_calculation(
    country_code: str,
    product_category: str,
    period_start: str,
    period_end: str,
) -> dict | None:
    resp = requests.post(
        f"{_base_url()}/api/v1/calculations",
        json={
            "country_code": country_code,
            "product_category": product_category,
            "period_start": period_start,
            "period_end": period_end,
        },
        headers=_headers(),
        timeout=30,
    )
    return _handle(resp)


def list_obligations() -> list[dict]:
    resp = requests.get(
        f"{_base_url()}/api/v1/calculations",
        headers=_headers(),
        timeout=10,
    )
    return _handle(resp)


def finalise_obligation(obligation_id: str) -> dict:
    resp = requests.post(
        f"{_base_url()}/api/v1/calculations/{obligation_id}/finalise",
        headers=_headers(),
        timeout=10,
    )
    return _handle(resp)


def delete_obligation(obligation_id: str) -> None:
    resp = requests.delete(
        f"{_base_url()}/api/v1/calculations/{obligation_id}",
        headers=_headers(),
        timeout=10,
    )
    _handle(resp)


# ---------------------------------------------------------------------------
# Submissions
# ---------------------------------------------------------------------------

def submit_obligation(obligation_id: str, submission_method: str) -> dict | None:
    resp = requests.post(
        f"{_base_url()}/api/v1/submissions",
        json={"obligation_id": obligation_id, "submission_method": submission_method},
        headers=_headers(),
        timeout=30,
    )
    return _handle(resp)


def list_submissions(obligation_id: str | None = None) -> list[dict]:
    params = {}
    if obligation_id:
        params["obligation_id"] = obligation_id
    resp = requests.get(
        f"{_base_url()}/api/v1/submissions",
        headers=_headers(),
        params=params,
        timeout=10,
    )
    return _handle(resp)


def acknowledge_submission(submission_id: str) -> dict:
    resp = requests.post(
        f"{_base_url()}/api/v1/submissions/{submission_id}/acknowledge",
        headers=_headers(),
        timeout=10,
    )
    return _handle(resp)


def download_submission_report(submission_id: str) -> bytes | None:
    resp = requests.get(
        f"{_base_url()}/api/v1/submissions/{submission_id}/download",
        headers=_headers(),
        timeout=30,
    )
    if not resp.ok:
        return None
    return resp.content
