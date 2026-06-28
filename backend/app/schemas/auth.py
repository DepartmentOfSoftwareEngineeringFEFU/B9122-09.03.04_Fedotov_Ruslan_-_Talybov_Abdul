from typing import Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class UserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=100)
    email: EmailStr
    password: str = Field(min_length=6, max_length=128)
    tinkoff_token: Optional[str] = Field(default=None, min_length=10, max_length=500)

    @field_validator("tinkoff_token", mode="before")
    @classmethod
    def blank_token_to_none(cls, value):
        if value is None:
            return None
        stripped = str(value).strip()
        return stripped or None


class UserLogin(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class TinkoffTokenUpdate(BaseModel):
    tinkoff_token: str = Field(min_length=10, max_length=500)

    @field_validator("tinkoff_token")
    @classmethod
    def strip_token(cls, value: str) -> str:
        return value.strip()


class TinkoffTokenUpdateResponse(BaseModel):
    status: str
    has_tinkoff_token: bool
    tinkoff_token_masked: Optional[str] = None


class UserResponse(BaseModel):
    id: int
    username: str
    email: EmailStr
    has_tinkoff_token: bool = False
    tinkoff_token_masked: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)
