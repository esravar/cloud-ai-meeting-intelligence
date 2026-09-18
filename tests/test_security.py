import uuid

import pytest

from app.security import (
    AuthenticationError,
    FieldCipher,
    PasswordService,
    TokenService,
)
from tests.test_llm import make_settings


def test_field_cipher_round_trip_and_hides_plaintext() -> None:
    cipher = FieldCipher(make_settings().field_encryption_key)

    encrypted = cipher.encrypt("confidential transcript")

    assert b"confidential transcript" not in encrypted
    assert cipher.decrypt(encrypted) == "confidential transcript"


def test_password_hash_round_trip() -> None:
    passwords = PasswordService()
    encoded = passwords.hash("a-long-test-password")

    assert encoded != "a-long-test-password"
    assert passwords.verify("a-long-test-password", encoded)
    assert not passwords.verify("wrong-password", encoded)


def test_token_round_trip() -> None:
    user_id = uuid.uuid4()
    tokens = TokenService("test-secret", 60)

    token = tokens.create(user_id)

    assert tokens.decode_user_id(token) == user_id
    with pytest.raises(AuthenticationError):
        tokens.decode_user_id(f"{token}broken")
