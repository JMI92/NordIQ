"""Google Drive service for creating and managing customer folders.

Requires env vars:
  GOOGLE_SERVICE_ACCOUNT_JSON      - full JSON string of service account key
  DRIVE_CUSTOMER_ROOT_FOLDER_ID    - ID of the Uusio/Customer-folder in Drive

If credentials are not configured the service degrades gracefully:
create_customer_folder() returns None and logs a warning.
"""

import asyncio
import json
import logging
import os
from functools import partial
from typing import Optional

logger = logging.getLogger(__name__)

DRIVE_SCOPES = ["https://www.googleapis.com/auth/drive"]
CUSTOMER_ROOT_FOLDER_ID = os.getenv(
    "DRIVE_CUSTOMER_ROOT_FOLDER_ID",
    "1YI4bQu8cxtCYbfGcrA9KJyS6nO_xeVz3",
)


def _get_drive_service():
    """Build a Drive v3 service from service account JSON env var."""
    sa_json = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON")
    if not sa_json:
        return None
    try:
        from google.oauth2 import service_account
        from googleapiclient.discovery import build

        info = json.loads(sa_json)
        creds = service_account.Credentials.from_service_account_info(
            info, scopes=DRIVE_SCOPES
        )
        return build("drive", "v3", credentials=creds, cache_discovery=False)
    except Exception:
        logger.exception("Failed to initialise Google Drive service")
        return None


def _create_folder_sync(name: str, parent_id: str) -> Optional[str]:
    """Synchronous Drive folder creation. Run in thread executor."""
    service = _get_drive_service()
    if service is None:
        return None
    try:
        metadata = {
            "name": name,
            "mimeType": "application/vnd.google-apps.folder",
            "parents": [parent_id],
        }
        folder = (
            service.files()
            .create(body=metadata, fields="id,name")
            .execute()
        )
        folder_id = folder.get("id")
        logger.info("Created Drive folder '%s' (id=%s)", name, folder_id)
        return folder_id
    except Exception:
        logger.exception("Failed to create Drive folder '%s'", name)
        return None


async def create_customer_folder(customer_name: str) -> Optional[str]:
    """Create a Drive subfolder for a customer and return its ID.

    Returns None if Drive is not configured or the API call fails.
    Caller should store the returned ID on the Customer.drive_folder_id field.
    """
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        None,
        partial(_create_folder_sync, customer_name, CUSTOMER_ROOT_FOLDER_ID),
    )
