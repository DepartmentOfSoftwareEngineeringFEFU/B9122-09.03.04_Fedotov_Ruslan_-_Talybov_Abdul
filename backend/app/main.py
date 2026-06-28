import asyncio
import logging

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from app.api import (
    routes_accounts,
    routes_analytics,
    routes_auth,
    routes_backtest,
    routes_bot_trades,
    routes_market,
    routes_model,
    routes_stock,
    routes_trade,
)
from app.core.config import settings
from app.core.db import check_db
from app.core.logging import RequestIdMiddleware, configure_logging
from app.services.auto_sell_service import run_auto_sell_worker
from app.services.random_bulk_trade_service import run_random_bulk_worker

# Import new ORM models before init_db/create_all.
from app.models.backtest_result import BacktestResult  # noqa: F401
from app.models.bot_trade import BotTrade  # noqa: F401
from app.models.bulk_trade import BulkTradeBatch, BulkTradeItem  # noqa: F401
from app.models.ml_model import MLModel  # noqa: F401
from app.models.model_forecast import ModelForecast  # noqa: F401
from app.models.order import Order  # noqa: F401
from app.models.stock import Stock, StockPrice  # noqa: F401
from app.models.trade import Trade  # noqa: F401
from app.models.training_session import TrainingSession  # noqa: F401

configure_logging()
logger = logging.getLogger(__name__)

app = FastAPI(title="Trading Backend (Tinkoff Sandbox)")
app.add_middleware(RequestIdMiddleware)

origins = [
    "http://127.0.0.1:3000",
    "http://127.0.0.1:3001",
    "http://localhost:3000",
    "http://localhost:3001",
    "http://192.168.0.72:3000",
    "http://192.168.0.72:3001",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _error_message(detail, fallback: str) -> str:
    if isinstance(detail, str):
        return detail
    if isinstance(detail, dict) and isinstance(detail.get("message"), str):
        return detail["message"]
    return fallback


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    request_id = getattr(request.state, "request_id", None)
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": f"HTTP_{exc.status_code}",
            "message": _error_message(exc.detail, "Request failed"),
            "detail": exc.detail,
            "details": {"request_id": request_id} if request_id else {},
        },
        headers=getattr(exc, "headers", None),
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    request_id = getattr(request.state, "request_id", None)
    return JSONResponse(
        status_code=422,
        content={
            "error": "VALIDATION_ERROR",
            "message": "Некорректные данные запроса",
            "detail": exc.errors(),
            "details": {"path": str(request.url.path), "request_id": request_id},
        },
    )


@app.on_event("startup")
async def startup():
    try:
        check_db()
    except Exception as exc:
        logger.exception("Database health check failed: %s", exc)

    if settings.AUTO_SELL_WORKER_ENABLED:
        app.state.auto_sell_task = asyncio.create_task(
            run_auto_sell_worker(settings.AUTO_SELL_POLL_SECONDS)
        )
        logger.info("Auto-sell worker enabled")
    else:
        app.state.auto_sell_task = None

    if settings.BULK_TRADE_WORKER_ENABLED:
        app.state.random_bulk_task = asyncio.create_task(
            run_random_bulk_worker(settings.BULK_TRADE_WORKER_POLL_SECONDS)
        )
        logger.info("Random bulk worker enabled")
    else:
        app.state.random_bulk_task = None


@app.on_event("shutdown")
async def shutdown():
    task = getattr(app.state, "auto_sell_task", None)
    if task:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            logger.info("Auto-sell worker stopped")

    bulk_task = getattr(app.state, "random_bulk_task", None)
    if bulk_task:
        bulk_task.cancel()
        try:
            await bulk_task
        except asyncio.CancelledError:
            logger.info("Random bulk worker stopped")


app.include_router(routes_market.router)
app.include_router(routes_analytics.router)
app.include_router(routes_bot_trades.router)
app.include_router(routes_model.router)
app.include_router(routes_trade.router)
app.include_router(routes_backtest.router)
app.include_router(routes_auth.router)
app.include_router(routes_accounts.router)
app.include_router(routes_stock.router)


@app.get("/")
def root():
    return {"message": "Trading backend is running"}


@app.get("/health")
def health():
    try:
        check_db()
        return {"status": "ok", "database": "ok"}
    except Exception as exc:
        detail = str(exc)
        response = {"status": "degraded", "database": "error", "detail": detail}
        if "cryptography" in detail and "caching_sha2_password" in detail:
            response["hint"] = (
                "Your current MySQL user uses caching_sha2_password. "
                "Run `docker compose down -v` and `docker compose up -d db` "
                "to recreate the local dev DB with mysql_native_password."
            )
        return response
