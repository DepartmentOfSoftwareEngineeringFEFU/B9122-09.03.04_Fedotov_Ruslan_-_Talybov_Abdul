import logging

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.auth import clear_auth_cookie, get_current_user, set_auth_cookie
from app.core.config import settings
from app.core.crypto import encrypt_tinkoff_token
from app.core.rate_limit import login_rate_limiter
from app.core.security import create_access_token, hash_password, verify_password
from app.core.tinkoff_client import validate_tinkoff_token
from app.models.user import User
from app.schemas.auth import (
    TinkoffTokenUpdate,
    TinkoffTokenUpdateResponse,
    UserCreate,
    UserLogin,
    UserResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])


def _validate_tinkoff_token(token: str) -> None:
    try:
        validate_tinkoff_token(token, use_sandbox=settings.USE_SANDBOX)
    except Exception as exc:
        logger.warning("T-Invest token validation failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="T-Invest API token is invalid or unavailable",
        )



@router.post("/register", response_model=UserResponse)
def register(user_in: UserCreate, db: Session = Depends(get_db)):
    if db.query(User).filter(User.email == user_in.email).first():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered")

    if db.query(User).filter(User.username == user_in.username).first():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Username already taken")

    user = User(
        username=user_in.username,
        email=user_in.email,
        password=hash_password(user_in.password),
        tinkoff_token=encrypt_tinkoff_token(user_in.tinkoff_token),
    )

    try:
        db.add(user)
        db.commit()
        db.refresh(user)
    except Exception:
        db.rollback()
        logger.exception("Registration failed for %s", user_in.email)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Registration failed")

    return user


@router.post("/login")
def login(user_in: UserLogin, request: Request, response: Response, db: Session = Depends(get_db)):
    login_rate_limiter.check(request, user_in.email)

    user = db.query(User).filter(User.email == user_in.email).first()
    if not user or not verify_password(user_in.password, user.password):
        login_rate_limiter.register_failure(request, user_in.email)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    login_rate_limiter.reset(request, user_in.email)
    token = create_access_token({"sub": str(user.id)})
    set_auth_cookie(response, token)
    return {"message": "Logged in", "user": UserResponse.model_validate(user)}


@router.post("/logout")
def logout(response: Response):
    clear_auth_cookie(response)
    return {"message": "Logged out"}


@router.get("/me", response_model=UserResponse)
def me(current_user: User = Depends(get_current_user)):
    return current_user


@router.put("/settings/tinkoff-token", response_model=TinkoffTokenUpdateResponse)
def update_tinkoff_token(
    payload: TinkoffTokenUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    token = payload.tinkoff_token.strip()
    _validate_tinkoff_token(token)

    current_user.tinkoff_token = encrypt_tinkoff_token(token)
    try:
        db.add(current_user)
        db.commit()
        db.refresh(current_user)
    except Exception:
        db.rollback()
        logger.exception("Failed to update T-Invest token for user_id=%s", current_user.id)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Token update failed")

    return {
        "status": "ok",
        "has_tinkoff_token": current_user.has_tinkoff_token,
        "tinkoff_token_masked": current_user.tinkoff_token_masked,
    }
