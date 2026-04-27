from __future__ import annotations

from secrets import token_urlsafe


def generate_opaque_token(byte_length: int = 32) -> str:
    return token_urlsafe(byte_length)
