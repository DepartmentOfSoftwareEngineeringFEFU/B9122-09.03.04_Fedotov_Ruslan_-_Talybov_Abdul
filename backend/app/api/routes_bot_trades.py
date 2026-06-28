from pathlib import Path
from typing import List

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.core.config import settings
from app.core.db import get_db
from app.models.user import User
from app.schemas.model import (
    AutoSellProcessResponse,
    AutoSellStatusResponse,
    BotTradeAnalyticsResponse,
    BotTradeConfirmRequest,
    BotTradeResponse,
    RandomBulkBatchResponse,
    RandomBulkStartRequest,
)
from app.services.auto_sell_service import count_auto_sell_candidates, process_due_auto_sells
from app.services.bot_trade_service import confirm_bot_trade, get_bot_trade_analytics, list_bot_trades
from app.services.random_bulk_trade_service import (
    assert_random_bulk_start_allowed,
    create_random_bulk_batch,
    get_latest_user_bulk_batch,
    get_user_bulk_batch,
    list_user_bulk_batches,
    process_random_bulk_batch,
    serialize_bulk_batch,
    sync_bulk_batch_from_trades,
)

router = APIRouter(prefix="/bot-trades", tags=["Bot Trades"])


@router.post("/confirm", response_model=BotTradeResponse)
def confirm_action(
    request: BotTradeConfirmRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Подтверждение действия AI-модели. Без этого endpoint сделки не исполняются."""
    return confirm_bot_trade(db=db, user_id=current_user.id, request=request)


@router.get("/history", response_model=List[BotTradeResponse])
def history(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    account_id: str | None = Query(default=None, max_length=128),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """История сделок, созданных только AI-ботом, без смешивания с ручными trades."""
    return list_bot_trades(db=db, user_id=current_user.id, limit=limit, offset=offset, account_id=account_id)


@router.get("/analytics", response_model=BotTradeAnalyticsResponse)
def analytics(
    account_id: str | None = Query(default=None, max_length=128),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Агрегаты доходности только по bot_trades."""
    return get_bot_trade_analytics(db=db, user_id=current_user.id, account_id=account_id)


@router.get("/auto-sell/status", response_model=AutoSellStatusResponse)
def auto_sell_status(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Безопасный статус backend auto-sell без исполнения ордеров."""
    counts = count_auto_sell_candidates(db, user_id=current_user.id)
    return {
        "enabled": bool(settings.AUTO_SELL_WORKER_ENABLED),
        "manual_process_enabled": bool(settings.AUTO_SELL_MANUAL_PROCESS_ENABLED),
        "poll_seconds": int(settings.AUTO_SELL_POLL_SECONDS),
        "mode": "sandbox" if settings.USE_SANDBOX else "real",
        "real_trading_enabled": bool(settings.AI_BOT_REAL_TRADING_ENABLED),
        "dry_run": bool(settings.AUTO_SELL_DRY_RUN),
        **counts,
    }


@router.post("/auto-sell/process", response_model=AutoSellProcessResponse)
def process_auto_sell_once(
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Manual auto-sell cycle for controlled dev/sandbox checks.

    Disabled by default to avoid an accidental public destructive endpoint.
    Enable only explicitly through AUTO_SELL_MANUAL_PROCESS_ENABLED=true.
    """
    if not settings.AUTO_SELL_MANUAL_PROCESS_ENABLED:
        raise HTTPException(
            status_code=403,
            detail="Manual auto-sell processing is disabled. Set AUTO_SELL_MANUAL_PROCESS_ENABLED=true for controlled dev/sandbox checks.",
        )
    summary = process_due_auto_sells(db=db, limit=limit, user_id=current_user.id)
    return {"status": "ok", **summary}


@router.post("/random-bulk/start", response_model=RandomBulkBatchResponse)
def start_random_bulk(
    request: RandomBulkStartRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    assert_random_bulk_start_allowed(has_tinkoff_token=current_user.has_tinkoff_token)
    batch = create_random_bulk_batch(
        db=db,
        user_id=current_user.id,
        account_id=request.account_id,
        target_count=request.target_count,
    )
    background_tasks.add_task(process_random_bulk_batch, batch.id)
    return serialize_bulk_batch(db, batch)


@router.get("/random-bulk", response_model=List[RandomBulkBatchResponse])
def list_random_bulk(
    limit: int = Query(5, ge=1, le=20),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    batches = list_user_bulk_batches(db=db, user_id=current_user.id, limit=limit)
    return [serialize_bulk_batch(db, batch, include_items=False) for batch in batches]


@router.get("/random-bulk/latest", response_model=RandomBulkBatchResponse)
def get_latest_random_bulk(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    batch = get_latest_user_bulk_batch(db=db, user_id=current_user.id)
    refreshed = sync_bulk_batch_from_trades(db, batch.id) or batch
    return serialize_bulk_batch(db, refreshed)


@router.get("/random-bulk/{batch_id}", response_model=RandomBulkBatchResponse)
def get_random_bulk(
    batch_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    batch = get_user_bulk_batch(db=db, user_id=current_user.id, batch_id=batch_id)
    refreshed = sync_bulk_batch_from_trades(db, batch.id) or batch
    return serialize_bulk_batch(db, refreshed)


@router.get("/random-bulk/{batch_id}/csv")
def download_random_bulk_csv(
    batch_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    batch = get_user_bulk_batch(db=db, user_id=current_user.id, batch_id=batch_id)
    if batch.status not in {"completed", "partial_completed", "failed"}:
        raise HTTPException(status_code=409, detail="CSV is not ready yet")
    if not batch.csv_path:
        raise HTTPException(status_code=404, detail="CSV file is not available")

    path = Path(batch.csv_path)
    if not path.exists() or not path.is_file():
        raise HTTPException(status_code=404, detail="CSV file is not found")

    return FileResponse(
        path=str(path),
        media_type="text/csv",
        filename=f"random_bulk_batch_{batch.id}.csv",
    )
