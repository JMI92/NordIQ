"""Tests for security helpers — JWT and credential encryption."""

import pytest
from jose import JWTError

from uusio.core.security import (
    create_access_token,
    decode_access_token,
    decrypt_config,
    encrypt_config,
    hash_password,
    verify_password,
)


def test_password_hash_and_verify():
    hashed = hash_password("s3cure-p@ssword!")
    assert verify_password("s3cure-p@ssword!", hashed)
    assert not verify_password("wrong-password", hashed)


def test_jwt_round_trip():
    token = create_access_token(subject="user-123", customer_id="customer-456")
    payload = decode_access_token(token)
    assert payload["sub"] == "user-123"
    assert payload["customer_id"] == "customer-456"


def test_jwt_invalid_token_raises():
    with pytest.raises(JWTError):
        decode_access_token("not.a.valid.token")


def test_encrypt_decrypt_config():
    config = {
        "account": "my_account",
        "user": "my_user",
        "password": "super_secret",
        "warehouse": "COMPUTE_WH",
    }
    ciphertext = encrypt_config(config)
    assert "super_secret" not in ciphertext  # must not be plaintext
    decrypted = decrypt_config(ciphertext)
    assert decrypted == config
