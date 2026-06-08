"""Authentication helpers: JWT tokens and credential encryption."""

import base64
import json
from datetime import datetime, timedelta, timezone

from cryptography.fernet import Fernet
from jose import JWTError, jwt
from passlib.context import CryptContext

from nordiq.core.config import get_settings

settings = get_settings()

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

ALGORITHM = "HS256"


# ---------------------------------------------------------------------------
# Password helpers
# ---------------------------------------------------------------------------

def hash_password(plain: str) -> str:
    return pwd_context.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


# ---------------------------------------------------------------------------
# JWT
# ---------------------------------------------------------------------------

def create_access_token(subject: str, customer_id: str) -> str:
    """Create a signed JWT embedding user identity and tenant (customer_id)."""
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_expire_minutes)
    payload = {"sub": subject, "customer_id": customer_id, "exp": expire}
    return jwt.encode(payload, settings.secret_key, algorithm=ALGORITHM)


def decode_access_token(token: str) -> dict:
    """Decode and validate a JWT. Raises JWTError on failure."""
    return jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])


# ---------------------------------------------------------------------------
# Credential encryption (for DataSource connection configs)
# ---------------------------------------------------------------------------

def _get_fernet() -> Fernet:
    key = settings.encryption_key
    if not key:
        # In development, derive a deterministic key from the secret_key.
        # NEVER do this in production.
        raw = (settings.secret_key + "0" * 32)[:32].encode()
        key = base64.urlsafe_b64encode(raw)
    return Fernet(key)


def encrypt_config(config: dict) -> str:
    """Serialize and encrypt a connector configuration dict."""
    plaintext = json.dumps(config).encode()
    return _get_fernet().encrypt(plaintext).decode()


def decrypt_config(ciphertext: str) -> dict:
    """Decrypt and deserialize a connector configuration dict."""
    plaintext = _get_fernet().decrypt(ciphertext.encode())
    return json.loads(plaintext)
