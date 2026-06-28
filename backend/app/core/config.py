from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


DEV_SECRET_KEY = "dev-secret-key-change-me"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", case_sensitive=True)

    APP_NAME: str = "Trading Backend"
    APP_ENV: str = Field(default="development", description="development | test | production")

    MYSQL_USER: str = "user"
    MYSQL_PASSWORD: str = "password"
    MYSQL_HOST: str = "127.0.0.1"
    MYSQL_PORT: int = 3306
    MYSQL_DB: str = "trading"

    TINKOFF_API_KEY: str = ""
    USE_SANDBOX: bool = True
    SECRET_KEY: str = DEV_SECRET_KEY
    TOKEN_ENCRYPTION_KEY: str = ""

    AUTH_COOKIE_NAME: str = "access_token"
    AUTH_COOKIE_SECURE: bool = False
    AUTH_COOKIE_HTTPONLY: bool = True
    AUTH_COOKIE_SAMESITE: str = "lax"
    AUTH_COOKIE_MAX_AGE_SECONDS: int = 3600

    LOGIN_RATE_LIMIT_ATTEMPTS: int = 5
    LOGIN_RATE_LIMIT_WINDOW_SECONDS: int = 300

    AUTO_SELL_WORKER_ENABLED: bool = False
    AUTO_SELL_POLL_SECONDS: int = 60
    AUTO_SELL_MANUAL_PROCESS_ENABLED: bool = False
    AUTO_SELL_DRY_RUN: bool = True
    AUTO_SELL_LOCK_NAME: str = "trade_master_auto_sell_worker"
    AI_BOT_REAL_TRADING_ENABLED: bool = False
    BULK_TRADE_WORKER_ENABLED: bool = False
    BULK_TRADE_WORKER_POLL_SECONDS: int = 60
    BULK_TRADE_CSV_DIR: str = "bulk_trade_exports"

    AI_FORECAST_MAX_SVR_SAMPLES: int = 900
    AI_FORECAST_MAX_GPR_SAMPLES: int = 450
    AI_FORECAST_MAX_ADAPTIVE_SAMPLES: int = 450

    DB_RUN_MIGRATIONS_ON_STARTUP: bool = False

    @property
    def is_production(self) -> bool:
        return self.APP_ENV.lower() == "production"

    @model_validator(mode="after")
    def validate_secure_settings(self):
        env = self.APP_ENV.lower()
        if env not in {"development", "dev", "test", "production", "prod", "stage", "staging"}:
            raise ValueError("APP_ENV must be development, test, staging or production")

        production_like = env in {"production", "prod", "stage", "staging"}
        if production_like:
            if not self.SECRET_KEY or self.SECRET_KEY == DEV_SECRET_KEY:
                raise ValueError("SECRET_KEY must be set to a non-default value outside development/test")
            if not self.AUTH_COOKIE_SECURE:
                raise ValueError("AUTH_COOKIE_SECURE must be true outside development/test")
            if not self.TOKEN_ENCRYPTION_KEY:
                raise ValueError("TOKEN_ENCRYPTION_KEY must be set outside development/test")

        samesite = self.AUTH_COOKIE_SAMESITE.lower()
        if samesite not in {"lax", "strict", "none"}:
            raise ValueError("AUTH_COOKIE_SAMESITE must be lax, strict or none")
        if samesite == "none" and not self.AUTH_COOKIE_SECURE:
            raise ValueError("AUTH_COOKIE_SAMESITE=none requires AUTH_COOKIE_SECURE=true")
        return self


settings = Settings()
