"""Thin HTTP client for the Uusio API."""
from __future__ import annotations

import os
from typing import Any

import requests
import streamlit as st


class APIError(Exception):
    """Raised when the API returns a non-2xx response."""
    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail
        super().__init__(f"API {status_code}: {detail}")


def _base_url() -> str:
    return st.session_state.get("api_url") or os.getenv("API_URL", "http://localhost:8000")


def _headers() -> dict:
    token = st.session_state.get("token")
    return {"Authorization": f"Bearer {token}"} if token else {}


def _handle(response: requests.Response) -> Any:
    if response.status_code == 401:
        st.session_state.clear()
        st.error("Istunto vanhentunut — kirjaudu uudelleen.")
        st.stop()
    if not response.ok:
        try:
            detail = response.json().get("detail", response.text)
        except Exception:
            detail = response.text or str(response.status_code)
        raise APIError(response.status_code, detail)
    return None if response.status_code == 204 else response.json()


def _show_error(e: Exception) -> None:
    """Display an API error in the UI without stopping the page."""
    if isinstance(e, APIError):
        st.error(f"API-virhe {e.status_code}: {e.detail}")
    else:
        st.error(str(e))


# Auth
def login(username: str, password: str) -> dict:
    return _handle(requests.post(f"{_base_url()}/api/v1/auth/login", data={"username": username, "password": password}, timeout=10))

def get_me() -> dict:
    return _handle(requests.get(f"{_base_url()}/api/v1/auth/me", headers=_headers(), timeout=10))

def health() -> dict:
    resp = requests.get(f"{_base_url()}/health", timeout=5)
    return resp.json() if resp.ok else {"status": "unreachable"}


# Data sources
def list_data_sources() -> list[dict]:
    return _handle(requests.get(f"{_base_url()}/api/v1/data-sources", headers=_headers(), timeout=10))

def create_data_source(payload: dict) -> dict:
    return _handle(requests.post(f"{_base_url()}/api/v1/data-sources", json=payload, headers=_headers(), timeout=10))

def delete_data_source(ds_id: str) -> None:
    _handle(requests.delete(f"{_base_url()}/api/v1/data-sources/{ds_id}", headers=_headers(), timeout=10))

def test_data_source(ds_id: str) -> dict:
    return _handle(requests.post(f"{_base_url()}/api/v1/data-sources/{ds_id}/test", headers=_headers(), timeout=30))


# Products
def list_products(limit: int = 100, offset: int = 0) -> list[dict]:
    return _handle(requests.get(f"{_base_url()}/api/v1/products", headers=_headers(), params={"limit": limit, "offset": offset}, timeout=10))

def list_product_weights(product_id: str) -> list[dict]:
    return _handle(requests.get(f"{_base_url()}/api/v1/products/{product_id}/weights", headers=_headers(), timeout=10))

def upload_products_csv(file_bytes: bytes, filename: str) -> dict:
    return _handle(requests.post(f"{_base_url()}/api/v1/products/upload-csv", headers=_headers(), files={"file": (filename, file_bytes, "text/csv")}, timeout=60))


# Material composition
def get_composition(product_id: str) -> list[dict]:
    return _handle(requests.get(f"{_base_url()}/api/v1/products/{product_id}/composition", headers=_headers(), timeout=10))

def save_composition(product_id: str, payload: list[dict]) -> list[dict]:
    return _handle(requests.put(f"{_base_url()}/api/v1/products/{product_id}/composition", json=payload, headers=_headers(), timeout=10))


# Monthly volumes
def list_volumes(year: int | None = None, month: int | None = None) -> list[dict]:
    params = {}
    if year: params["year"] = year
    if month: params["month"] = month
    return _handle(requests.get(f"{_base_url()}/api/v1/volumes", headers=_headers(), params=params, timeout=10))

def upsert_volume(product_id: str, year: int, month: int, units_sold: float) -> dict:
    return _handle(requests.post(f"{_base_url()}/api/v1/volumes", json={"product_id": product_id, "year": year, "month": month, "units_sold": units_sold}, headers=_headers(), timeout=10))

def upload_volumes_csv(file_bytes: bytes, filename: str) -> dict:
    return _handle(requests.post(f"{_base_url()}/api/v1/volumes/upload-csv", headers=_headers(), files={"file": (filename, file_bytes)}, timeout=60))

def calculate_from_volumes(year: int, month: int) -> dict:
    return _handle(requests.post(f"{_base_url()}/api/v1/volumes/calculate", headers=_headers(), params={"year": year, "month": month}, timeout=30))


# Calculations
def run_calculation(country_code: str, product_category: str, period_start: str, period_end: str) -> dict | None:
    return _handle(requests.post(f"{_base_url()}/api/v1/calculations", json={"country_code": country_code, "product_category": product_category, "period_start": period_start, "period_end": period_end}, headers=_headers(), timeout=30))

def list_obligations() -> list[dict]:
    return _handle(requests.get(f"{_base_url()}/api/v1/calculations", headers=_headers(), timeout=10))

def finalise_obligation(obligation_id: str) -> dict:
    return _handle(requests.post(f"{_base_url()}/api/v1/calculations/{obligation_id}/finalise", headers=_headers(), timeout=10))

def delete_obligation(obligation_id: str) -> None:
    _handle(requests.delete(f"{_base_url()}/api/v1/calculations/{obligation_id}", headers=_headers(), timeout=10))


# Submissions
def submit_obligation(obligation_id: str, submission_method: str) -> dict | None:
    return _handle(requests.post(f"{_base_url()}/api/v1/submissions", json={"obligation_id": obligation_id, "submission_method": submission_method}, headers=_headers(), timeout=30))

def list_submissions(obligation_id: str | None = None) -> list[dict]:
    params = {"obligation_id": obligation_id} if obligation_id else {}
    return _handle(requests.get(f"{_base_url()}/api/v1/submissions", headers=_headers(), params=params, timeout=10))

def acknowledge_submission(submission_id: str) -> dict:
    return _handle(requests.post(f"{_base_url()}/api/v1/submissions/{submission_id}/acknowledge", headers=_headers(), timeout=10))

def download_submission_report(submission_id: str) -> bytes | None:
    resp = requests.get(f"{_base_url()}/api/v1/submissions/{submission_id}/download", headers=_headers(), timeout=30)
    return resp.content if resp.ok else None


# Admin
def admin_get_stats() -> dict:
    return _handle(requests.get(f"{_base_url()}/api/v1/admin/stats", headers=_headers(), timeout=10))

def admin_list_customers() -> list[dict]:
    return _handle(requests.get(f"{_base_url()}/api/v1/admin/customers", headers=_headers(), timeout=10))

def admin_update_customer(customer_id: str, payload: dict) -> dict:
    return _handle(requests.patch(f"{_base_url()}/api/v1/admin/customers/{customer_id}", json=payload, headers=_headers(), timeout=10))

def admin_list_users(customer_id: str) -> list[dict]:
    return _handle(requests.get(f"{_base_url()}/api/v1/admin/customers/{customer_id}/users", headers=_headers(), timeout=10))

def admin_reset_password(user_id: str) -> dict:
    return _handle(requests.post(f"{_base_url()}/api/v1/admin/users/{user_id}/reset-password", headers=_headers(), timeout=10))

def admin_update_user(user_id: str, payload: dict) -> dict:
    return _handle(requests.patch(f"{_base_url()}/api/v1/admin/users/{user_id}", json=payload, headers=_headers(), timeout=10))


# Billing
def list_invoices(customer_id: str | None = None, status: str | None = None) -> list[dict]:
    params = {}
    if customer_id: params["customer_id"] = customer_id
    if status: params["status"] = status
    return _handle(requests.get(f"{_base_url()}/api/v1/billing", headers=_headers(), params=params, timeout=10))

def create_invoice(payload: dict) -> dict:
    return _handle(requests.post(f"{_base_url()}/api/v1/billing", json=payload, headers=_headers(), timeout=10))

def update_invoice(invoice_id: str, payload: dict) -> dict:
    return _handle(requests.patch(f"{_base_url()}/api/v1/billing/{invoice_id}", json=payload, headers=_headers(), timeout=10))

def delete_invoice(invoice_id: str) -> None:
    _handle(requests.delete(f"{_base_url()}/api/v1/billing/{invoice_id}", headers=_headers(), timeout=10))


# Regulations
def list_regulations(country_code: str | None = None, category: str | None = None, search: str | None = None, active_only: bool = True) -> list[dict]:
    params: dict = {"active_only": active_only}
    if country_code: params["country_code"] = country_code
    if category: params["category"] = category
    if search: params["search"] = search
    return _handle(requests.get(f"{_base_url()}/api/v1/regulations", headers=_headers(), params=params, timeout=10))

def create_regulation(payload: dict) -> dict:
    return _handle(requests.post(f"{_base_url()}/api/v1/regulations", json=payload, headers=_headers(), timeout=10))

def update_regulation(entry_id: str, payload: dict) -> dict:
    return _handle(requests.patch(f"{_base_url()}/api/v1/regulations/{entry_id}", json=payload, headers=_headers(), timeout=10))

def delete_regulation(entry_id: str) -> None:
    _handle(requests.delete(f"{_base_url()}/api/v1/regulations/{entry_id}", headers=_headers(), timeout=10))


# PRO Registry
def list_pros(country_code: str | None = None, category: str | None = None, active_only: bool = True) -> list[dict]:
    params: dict = {"active_only": active_only}
    if country_code: params["country_code"] = country_code
    if category: params["category"] = category
    return _handle(requests.get(f"{_base_url()}/api/v1/pro-registry/pros", headers=_headers(), params=params, timeout=10))

def create_pro(payload: dict) -> dict:
    return _handle(requests.post(f"{_base_url()}/api/v1/pro-registry/pros", json=payload, headers=_headers(), timeout=10))

def update_pro(pro_id: str, payload: dict) -> dict:
    return _handle(requests.patch(f"{_base_url()}/api/v1/pro-registry/pros/{pro_id}", json=payload, headers=_headers(), timeout=10))

def delete_pro(pro_id: str) -> None:
    _handle(requests.delete(f"{_base_url()}/api/v1/pro-registry/pros/{pro_id}", headers=_headers(), timeout=10))

def list_registrations(customer_id: str | None = None) -> list[dict]:
    params = {"customer_id": customer_id} if customer_id else {}
    return _handle(requests.get(f"{_base_url()}/api/v1/pro-registry/registrations", headers=_headers(), params=params, timeout=10))

def create_registration(payload: dict) -> dict:
    return _handle(requests.post(f"{_base_url()}/api/v1/pro-registry/registrations", json=payload, headers=_headers(), timeout=10))

def update_registration(reg_id: str, payload: dict) -> dict:
    return _handle(requests.patch(f"{_base_url()}/api/v1/pro-registry/registrations/{reg_id}", json=payload, headers=_headers(), timeout=10))

def delete_registration(reg_id: str) -> None:
    _handle(requests.delete(f"{_base_url()}/api/v1/pro-registry/registrations/{reg_id}", headers=_headers(), timeout=10))


# Portal
def portal_summary() -> dict:
    return _handle(requests.get(f"{_base_url()}/api/v1/portal/summary", headers=_headers(), timeout=10))

def my_registrations() -> list[dict]:
    return _handle(requests.get(f"{_base_url()}/api/v1/portal/registrations", headers=_headers(), timeout=10))

def reporting_calendar() -> list[dict]:
    return _handle(requests.get(f"{_base_url()}/api/v1/portal/reporting-calendar", headers=_headers(), timeout=10))

def my_reports() -> list[dict]:
    return _handle(requests.get(f"{_base_url()}/api/v1/portal/reports", headers=_headers(), timeout=10))

def list_my_files(folder: str | None = None) -> list[dict]:
    params = {"folder": folder} if folder else {}
    return _handle(requests.get(f"{_base_url()}/api/v1/portal/files", headers=_headers(), params=params, timeout=10))

def upload_my_file(data: bytes, filename: str, folder: str = "contracts") -> dict:
    return _handle(requests.post(
        f"{_base_url()}/api/v1/portal/files/upload",
        headers=_headers(),
        params={"folder": folder},
        files={"file": (filename, data)},
        timeout=60,
    ))
