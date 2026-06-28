from __future__ import annotations

import base64
import hashlib
import logging

from app.core.config import settings

logger = logging.getLogger(__name__)

ENCRYPTED_PREFIX = "enc:"

try:
    from cryptography.fernet import Fernet, InvalidToken
except ModuleNotFoundError:  # pragma: no cover - depends on local environment
    Fernet = None

    class InvalidToken(Exception):
        pass


class CryptoDependencyError(RuntimeError):
    """Raised when token encryption is used without the cryptography package."""


def _key_material() -> str:
    return settings.TOKEN_ENCRYPTION_KEY or settings.SECRET_KEY


def _fernet() -> Fernet:
    if Fernet is None:
        raise CryptoDependencyError(
            "The 'cryptography' package is required for T-Invest token encryption. "
            "Install backend dependencies with `python -m pip install -r requirements.txt`."
        )
    digest = hashlib.sha256(_key_material().encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def encrypt_tinkoff_token(token: str | None) -> str | None:
    if not token:
        return None
    stripped = token.strip()
    if not stripped:
        return None
    if stripped.startswith(ENCRYPTED_PREFIX):
        return stripped
    return ENCRYPTED_PREFIX + _fernet().encrypt(stripped.encode("utf-8")).decode("utf-8")


def decrypt_tinkoff_token(value: str | None) -> str | None:
    if not value:
        return None
    stripped = value.strip()
    if not stripped:
        return None
    if not stripped.startswith(ENCRYPTED_PREFIX):
        # Legacy dev data. It is intentionally accepted so existing local DBs do
        # not break, but new writes always use encrypt_tinkoff_token().
        return stripped
    try:
        payload = stripped[len(ENCRYPTED_PREFIX):]
        return _fernet().decrypt(payload.encode("utf-8")).decode("utf-8")
    except InvalidToken:
        logger.warning("Encrypted T-Invest token could not be decrypted")
        return None


def mask_secret(value: str | None) -> str | None:
    try:
        plain = decrypt_tinkoff_token(value)
    except CryptoDependencyError:
        return "***" if value and value.strip().startswith(ENCRYPTED_PREFIX) else None
    if not plain:
        return None
    if len(plain) <= 6:
        return "***"
    return f"{plain[:2]}***{plain[-4:]}"
