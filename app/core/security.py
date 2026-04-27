from __future__ import annotations

import hashlib
import uuid
from datetime import UTC, datetime, timedelta
from secrets import token_urlsafe
from typing import Any

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from app.core.config import Settings, get_settings
from app.core.exceptions import PrepSuiteError

_password_hasher = PasswordHasher()
_ephemeral_private_key: str | None = None
_ephemeral_public_key: str | None = None


def generate_opaque_token(byte_length: int = 32) -> str:
    return token_urlsafe(byte_length)


def hash_secret(secret: str) -> str:
    return hashlib.sha256(secret.encode("utf-8")).hexdigest()


def hash_password(password: str) -> str:
    return _password_hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return _password_hasher.verify(password_hash, password)
    except VerifyMismatchError:
        return False


def password_needs_rehash(password_hash: str) -> bool:
    return _password_hasher.check_needs_rehash(password_hash)


def _generate_ephemeral_key_pair() -> tuple[str, str]:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("utf-8")
    public_pem = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("utf-8")
    return private_pem, public_pem


def get_jwt_key_pair(settings: Settings | None = None) -> tuple[str, str]:
    global _ephemeral_private_key, _ephemeral_public_key
    current_settings = settings or get_settings()
    if current_settings.jwt_private_key_pem and current_settings.jwt_public_key_pem:
        return current_settings.jwt_private_key_pem, current_settings.jwt_public_key_pem
    if _ephemeral_private_key is None or _ephemeral_public_key is None:
        _ephemeral_private_key, _ephemeral_public_key = _generate_ephemeral_key_pair()
    return _ephemeral_private_key, _ephemeral_public_key


def create_access_token(
    *,
    subject: uuid.UUID,
    tenant_id: uuid.UUID | None,
    user_type: str,
    settings: Settings | None = None,
    expires_delta: timedelta | None = None,
) -> str:
    current_settings = settings or get_settings()
    private_key, _ = get_jwt_key_pair(current_settings)
    now = datetime.now(UTC)
    expires_at = now + (
        expires_delta or timedelta(minutes=current_settings.access_token_ttl_minutes)
    )
    payload: dict[str, Any] = {
        "iss": current_settings.jwt_issuer,
        "aud": current_settings.jwt_audience,
        "sub": str(subject),
        "typ": "access",
        "jti": str(uuid.uuid4()),
        "user_type": user_type,
        "iat": int(now.timestamp()),
        "nbf": int(now.timestamp()),
        "exp": int(expires_at.timestamp()),
    }
    if tenant_id is not None:
        payload["tid"] = str(tenant_id)
    return jwt.encode(payload, private_key, algorithm="RS256")


def decode_access_token(token: str, settings: Settings | None = None) -> dict[str, Any]:
    current_settings = settings or get_settings()
    _, public_key = get_jwt_key_pair(current_settings)
    try:
        payload = jwt.decode(
            token,
            public_key,
            algorithms=["RS256"],
            audience=current_settings.jwt_audience,
            issuer=current_settings.jwt_issuer,
        )
    except jwt.PyJWTError as exc:
        raise PrepSuiteError(
            "invalid_token",
            "Access token is invalid or expired.",
            status_code=401,
        ) from exc
    if payload.get("typ") != "access":
        raise PrepSuiteError("invalid_token_type", "Expected an access token.", status_code=401)
    return payload


def get_bearer_token(authorization_header: str | None) -> str | None:
    if not authorization_header:
        return None
    scheme, _, token = authorization_header.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise PrepSuiteError(
            "invalid_authorization_header",
            "Authorization header must use the Bearer scheme.",
            status_code=401,
        )
    return token
