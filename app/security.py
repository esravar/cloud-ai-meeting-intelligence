import uuid
from datetime import datetime, timedelta, timezone

import jwt
from cryptography.fernet import Fernet, InvalidToken
from pwdlib import PasswordHash


class AuthenticationError(RuntimeError):
    pass


class EncryptionError(RuntimeError):
    pass


class PasswordService:
    def __init__(self):
        self._password_hash = PasswordHash.recommended()

    def hash(self, password: str) -> str:
        return self._password_hash.hash(password)

    def verify(self, password: str, password_hash: str) -> bool:
        return self._password_hash.verify(password, password_hash)


class TokenService:
    def __init__(self, secret_key: str, access_token_minutes: int):
        self._secret_key = secret_key
        self._access_token_minutes = access_token_minutes

    def create(self, user_id: uuid.UUID) -> str:
        now = datetime.now(timezone.utc)
        payload = {
            "sub": str(user_id),
            "iat": now,
            "exp": now + timedelta(minutes=self._access_token_minutes),
        }
        return jwt.encode(payload, self._secret_key, algorithm="HS256")

    def decode_user_id(self, token: str) -> uuid.UUID:
        try:
            payload = jwt.decode(token, self._secret_key, algorithms=["HS256"])
            return uuid.UUID(payload["sub"])
        except (jwt.InvalidTokenError, KeyError, ValueError) as exc:
            raise AuthenticationError("Invalid or expired access token.") from exc


class FieldCipher:
    def __init__(self, key: str):
        self._fernet = Fernet(key.encode())

    def encrypt(self, value: str) -> bytes:
        return self._fernet.encrypt(value.encode())

    def decrypt(self, value: bytes) -> str:
        try:
            return self._fernet.decrypt(value).decode()
        except InvalidToken as exc:
            raise EncryptionError("Encrypted database value cannot be read.") from exc
