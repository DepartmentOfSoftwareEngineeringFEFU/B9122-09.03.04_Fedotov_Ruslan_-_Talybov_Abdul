import logging
from typing import Any

from fastapi import Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.db import get_db
from app.core.security import decode_access_token
from app.models.user import User

logger = logging.getLogger(__name__)


def cookie_options() -> dict[str, Any]:
    return {
        "httponly": bool(settings.AUTH_COOKIE_HTTPONLY),
        "secure": bool(settings.AUTH_COOKIE_SECURE),
        "samesite": settings.AUTH_COOKIE_SAMESITE.lower(),
        "max_age": int(settings.AUTH_COOKIE_MAX_AGE_SECONDS),
        "path": "/",
    }


def set_auth_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=settings.AUTH_COOKIE_NAME,
        value=token,
        **cookie_options(),
    )


def clear_auth_cookie(response: Response) -> None:
    response.delete_cookie(
        key=settings.AUTH_COOKIE_NAME,
        path="/",
        httponly=bool(settings.AUTH_COOKIE_HTTPONLY),
        secure=bool(settings.AUTH_COOKIE_SECURE),
        samesite=settings.AUTH_COOKIE_SAMESITE.lower(),
    )


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    access_token = request.cookies.get(settings.AUTH_COOKIE_NAME)
    logger.debug("auth cookie present: %s", bool(access_token))

    if not access_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    payload = decode_access_token(access_token)
    if not payload or "sub" not in payload:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    try:
        user_id = int(payload["sub"])
    except (TypeError, ValueError):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token") from None

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        logger.info("user not found for auth token")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    return user
