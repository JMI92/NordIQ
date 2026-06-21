"""Thin HTTP client for the Uusio API.

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
    resp = requests.post(
        f"{_base_url()}/api/v1/auth/login",
        data={"username": username, "password": password},
        timeout=10,
    )
    return _handle(resp)


def get_me() -> dict:
    resp = requests.get(f"{_base_url()}/api/v1/auth/me", headers=_headers(), timeout=10)
    return _handle(resp)


def health() -> dict:
    resp = requests.get(f"{_base_url()}/health", timeout=5)
    return resp.json() if resp.ok else {"status": "unreachable"}


# ---------------------------------------------------------------------------
# Data sources
# ---------------------------------------------------------------------------

def list_data_sources() -> list[dict]:
    resp = requests.get(f"{_base_url()}/api/v1/data-sources", headers=_headers(), timeout=10)
    return _handle(resp)


def create_data_source(payload: dict) -> dict:
    resp = requests.post(f"{_base_url()}/api/v1/data-sources", json=payload, headers=_headers(), timeout=10)
    return _handle(resp)


def delete_data_source(ds_id: str) -> None:
    resp = requests.delete(f"{_base_url()}/api/v1/data-sources/{ds_id}", headers=_headers(), timeout=10)
    _handle(resp)


def test_data_source(ds_id: str) -> dict:
    resp = requests.post(f"{_base_url()}/api/v1/data-sources/{ds_id}/test", headers=_headers(), timeout=30)
    return _handle(resp)


# ---------------------------------------------------------------------------
# Products
# ---------------------------------------------------------------------------

def list_products(limit: int = 100, offset: int = 0) -> list[dict]:
    resp = requests.get(f"{_base_url()}/api/v1/products", headers=_headers(), params={"limit": limit, "offset": offset}, timeout=10)
    return _handle(resp)


def list_product_weights(product_id: str) -> list[dict]:
    resp = requests.get(f"{_base_url()}/api/v1/products/{product_id}/weights", headers=_headers(), timeout=10)
    return _handle(resp)


def upload_products_csv(file_bytes: bytes, filename: str) -> dict:
    resp = requests.post(f"{_base_url()}/api/v1/products/upload-csv", headers=_headers(), files={"file": (filename, file_bytes, "text/csv")}, timeout=60)
    return _handle(resp)


# ---------------------------------------------------------------------------
# Calculations
# ---------------------------------------------------------------------------

def run_calculation(country_code: str, product_category: str, period_start: str, period_end: str) -> dict | None:
    resp = requests.post(f"{_base_url()}/api/v1/calculations", json={"country_code": country_code, "product_category": product_category, "period_start": period_start, "period_end": period_end}, headers=_headers(), timeout=30)
    return _handle(resp)


def list_obligations() -> list[dict]:
    resp = requests.get(f"{_base_url()}/api/v1/calculations", headers=_headers(), timeout=10)
    return _handle(resp)


def finalise_obligation(obligation_id: str) -> dict:
    resp = requests.post(f"{_base_url()}/api/v1/calculations/{obligation_id}/finalise", headers=_headers(), timeout=10)
    return _handle(resp)


def delete_obligation(obligation_id: str) -> None:
    resp = requests.delete(f"{_base_url()}/api/v1/calculations/{obligation_id}", headers=_headers(), timeout=10)
    _handle(resp)


# ---------------------------------------------------------------------------
# Submissions
# ---------------------------------------------------------------------------

def submit_obligation(obligation_id: str, submission_method: str) -> dict | None:
    resp = requests.post(f"{_base_url()}/api/v1/submissions", json={"obligation_id": obligation_id, "submission_method": submission_method}, headers=_headers(), timeout=30)
    return _handle(resp)


def list_submissions(obligation_id: str | None = None) -> list[dict]:
    params = {"obligation_id": obligation_id} if obligation_id else {}
    resp = requests.get(f"{_base_url()}/api/v1/submissions", headers=_headers(), params=params, timeout=10)
    return _handle(resp)


def acknowledge_submission(submission_id: str) -> dict:
    resp = requests.post(f"{_base_url()}/api/v1/submissions/{submission_id}/acknowledge", headers=_headers(), timeout=10)
    return _handle(resp)


def download_submission_report(submission_id: str) -> bytes | None:
    resp = requests.get(f"{_base_url()}/api/v1/submissions/{submission_id}/download", headers=_headers(), timeout=30)
    return resp.content if resp.ok else None


# ---------------------------------------------------------------------------
# Admin
# ---------------------------------------------------------------------------

def admin_get_stats() -> dict:
    resp = requests.get(f"{_base_url()}/api/v1/admin/stats", headers=_headers(), timeout=10)
    return _handle(resp)


def admin_list_customers() -> list[dict]:
    resp = requests.get(f"{_base_url()}/api/v1/admin/customers", headers=_headers(), timeout=10)
    return _handle(resp)


def admin_update_customer(customer_id: str, payload: dict) -> dict:
    resp = requests.patch(f"{_base_url()}/api/v1/admin/customers/{customer_id}", json=payload, headers=_headers(), timeout=10)
    return _handle(resp)


def admin_list_users(customer_id: str) -> list[dict]:
    resp = requests.get(f"{_base_url()}/api/v1/admin/customers/{customer_id}/users", headers=_headers(), timeout=10)
    return _handle(resp)


def admin_reset_password(user_id: str) -> dict:
    resp = requests.post(f"{_base_url()}/api/v1/admin/users/{user_id}/reset-password", headers=_headers(), timeout=10)
    return _handle(resp)


def admin_update_user(user_id: str, payload: dict) -> dict:
    resp = requests.patch(f"{_base_url()}/api/v1/admin/users/{user_id}", json=payload, headers=_headers(), timeout=10)
    return _handle(resp)


# ---------------------------------------------------------------------------
# Billing
# ---------------------------------------------------------------------------

def list_invoices(customer_id: str | None = None, status: str | None = None) -> list[dict]:
    params = {}
    if customer_id:
        params["customer_id"] = customer_id
    if status:
        params["status"] = status
    resp = requests.get(f"{_base_url()}/api/v1/billing", headers=_headers(), params=params, timeout=10)
    return _handle(resp)


def create_invoice(payload: dict) -> dict:
    resp = requests.post(f"{_base_url()}/api/v1/billing", json=payload, headers=_headers(), timeout=10)
    return _handle(resp)


def update_invoice(invoice_id: str, payload: dict) -> dict:
    resp = requests.patch(f"{_base_url()}/api/v1/billing/{invoice_id}", json=payload, headers=_headers(), timeout=10)
    return _handle(resp)


def delete_invoice(invoice_id: str) -> None:
    resp = requests.delete(f"{_base_url()}/api/v1/billing/{invoice_id}", headers=_headers(), timeout=10)
    _handle(resp)


# ---------------------------------------------------------------------------
# Regulations
# ---------------------------------------------------------------------------

def list_regulations(country_code: str | None = None, category: str | None = None, search: str | None = None, active_only: bool = True) -> list[dict]:
    params: dict = {"active_only": active_only}
    if country_code:
        params["country_code"] = country_code
    if category:
        params["category"] = category
    if search:
        params["search"] = search
    resp = requests.get(f"{_base_url()}/api/v1/regulations", headers=_headers(), params=params, timeout=10)
    return _handle(resp)


def create_regulation(payload: dict) -> dict:
    resp = requests.post(f"{_base_url()}/api/v1/regulations", json=payload, headers=_headers(), timeout=10)
    return _handle(resp)


def update_regulation(entry_id: str, payload: dict) -> dict:
    resp = requests.patch(f"{_base_url()}/api/v1/regulations/{entry_id}", json=payload, headers=_headers(), timeout=10)
    return _handle(resp)


def delete_regulation(entry_id: str) -> None:
    resp = requests.delete(f"{_base_url()}/api/v1/regulations/{entry_id}", headers=_headers(), timeout=10)
    _handle(resp)
