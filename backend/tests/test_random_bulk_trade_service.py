from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.db import Base
from app.models import asset, backtest_result, ml_model, model_forecast, order, stock, trade, training_session  # noqa: F401
from app.models.bot_trade import BotTrade
from app.models.bulk_trade import BulkTradeBatch, BulkTradeItem
from app.models.user import User
from app.services import auto_sell_service, random_bulk_trade_service


def make_session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    db = Session()
    db.add(User(id=1, username="user", email="user@example.com", password="secret"))
    db.commit()
    return db, Session


def test_random_bulk_selects_positive_forecasts_and_stops_at_target(monkeypatch):
    db, Session = make_session()
    monkeypatch.setattr(random_bulk_trade_service, "SessionLocal", Session)
    monkeypatch.setattr(random_bulk_trade_service.random, "shuffle", lambda items: None)
    monkeypatch.setattr(random_bulk_trade_service, "list_popular_moex_shares", lambda **_kwargs: [])
    monkeypatch.setattr(random_bulk_trade_service, "list_moex_shares", lambda **_kwargs: [
        {"figi": "FIGI1", "ticker": "AAA", "currency": "RUB", "instrument_type": "share", "lot": 10, "current_price": 100},
        {"figi": "FIGI2", "ticker": "BBB", "currency": "RUB", "instrument_type": "share", "lot": 1, "current_price": 100},
        {"figi": "FIGI3", "ticker": "CCC", "currency": "RUB", "instrument_type": "share", "lot": 1, "current_price": 100},
    ])

    forecast_by_id = {}

    def fake_compare(db, user_id, request):
        forecast_id = len(forecast_by_id) + 1
        forecast_by_id[forecast_id] = request.figi
        return {
            "status": "success",
            "summary": {
                "best_forecast": {
                    "forecast_id": forecast_id,
                    "model_type": "svr",
                    "model_type_effective": "svr",
                    "current_price": 100.0,
                    "predicted_price": 101.0,
                    "price_delta_percent": 1.0,
                    "lot": 10 if request.figi == "FIGI1" else 1,
                    "metrics": {"validation_mae": 0.2, "MAE": 0.3},
                    "recommendation": {"action": "BUY_OPTIONAL"},
                }
            },
        }

    seen_requests = []

    def fake_confirm(db, user_id, request):
        seen_requests.append(request)
        scheduled_delta = request.scheduled_sell_at - datetime.now(timezone.utc)
        assert timedelta(minutes=59) <= scheduled_delta <= timedelta(hours=1, minutes=1)
        assert request.auto_sell_enabled is True
        assert request.auto_sell_target_enabled is False
        figi = forecast_by_id[request.forecast_id]
        trade = BotTrade(
            user_id=user_id,
            forecast_id=request.forecast_id,
            figi=figi,
            ticker=figi,
            source="bulk",
            account_id=request.account_id,
            horizon="1h",
            model_type_requested="svr",
            model_type_used="svr",
            side="buy",
            quantity=request.quantity,
            price=Decimal("100"),
            amount=Decimal(str(100 * request.quantity)),
            status="scheduled_sell",
            auto_sell_enabled=True,
            auto_sell_target_enabled=False,
            scheduled_sell_at=request.scheduled_sell_at,
            confirmed_at=datetime.now(timezone.utc),
            executed_at=datetime.now(timezone.utc),
        )
        db.add(trade)
        db.commit()
        db.refresh(trade)
        return trade

    monkeypatch.setattr(random_bulk_trade_service, "compare_forecast_models", fake_compare)
    monkeypatch.setattr(random_bulk_trade_service, "confirm_bot_trade", fake_confirm)

    batch = random_bulk_trade_service.create_random_bulk_batch(db, user_id=1, account_id="acc-1", target_count=2)
    random_bulk_trade_service.process_random_bulk_batch(batch.id)

    check = Session()
    stored = check.query(BulkTradeBatch).filter(BulkTradeBatch.id == batch.id).first()
    items = check.query(BulkTradeItem).filter(BulkTradeItem.batch_id == batch.id).order_by(BulkTradeItem.id).all()

    assert stored.status == "scheduled_sell"
    assert stored.bought_count == 2
    assert stored.scanned_count == 2
    assert len(seen_requests) == 2
    assert [request.quantity for request in seen_requests] == [10, 1]
    assert [item.status for item in items] == ["bought", "bought"]


def test_random_bulk_candle_errors_become_skipped(monkeypatch):
    db, Session = make_session()
    monkeypatch.setattr(random_bulk_trade_service, "SessionLocal", Session)
    monkeypatch.setattr(random_bulk_trade_service.random, "shuffle", lambda items: None)
    monkeypatch.setattr(random_bulk_trade_service, "list_popular_moex_shares", lambda **_kwargs: [])
    monkeypatch.setattr(random_bulk_trade_service, "list_moex_shares", lambda **_kwargs: [
        {"figi": "FIGI1", "ticker": "AAA", "currency": "RUB", "instrument_type": "share", "lot": 1, "current_price": 100},
    ])
    monkeypatch.setattr(random_bulk_trade_service, "compare_forecast_models", lambda **_kwargs: (_ for _ in ()).throw(
        ValueError("Недостаточно свечей для прогноза")
    ))
    monkeypatch.setattr(random_bulk_trade_service, "confirm_bot_trade", lambda **_kwargs: (_ for _ in ()).throw(
        AssertionError("Trade should not be executed")
    ))

    batch = random_bulk_trade_service.create_random_bulk_batch(db, user_id=1, account_id=None, target_count=1)
    random_bulk_trade_service.process_random_bulk_batch(batch.id)

    check = Session()
    stored = check.query(BulkTradeBatch).filter(BulkTradeBatch.id == batch.id).first()
    item = check.query(BulkTradeItem).filter(BulkTradeItem.batch_id == batch.id).first()

    assert stored.status == "partial_completed"
    assert stored.skipped_count == 1
    assert stored.failed_count == 0
    assert item.status == "skipped"
    assert item.reason == "insufficient_candles"


def test_random_bulk_skips_negative_forecast_and_writes_csv(monkeypatch):
    db, _Session = make_session()
    csv_dir = Path.cwd() / "backend" / "pytest_bulk_trade_exports"
    csv_dir.mkdir(exist_ok=True)
    monkeypatch.setattr(random_bulk_trade_service.settings, "BULK_TRADE_CSV_DIR", str(csv_dir))

    batch = random_bulk_trade_service.create_random_bulk_batch(db, user_id=1, account_id=None, target_count=30)
    item = BulkTradeItem(
        batch_id=batch.id,
        user_id=1,
        figi="FIGI1",
        ticker="AAA",
        status="skipped",
        reason="predicted_not_positive",
        current_price=Decimal("100"),
        predicted_price=Decimal("99"),
        price_delta_percent=Decimal("-1"),
    )
    db.add(item)
    batch.status = "partial_completed"
    batch.finished_at = datetime.now(timezone.utc)
    db.add(batch)
    db.commit()

    path = random_bulk_trade_service.generate_bulk_trade_csv(db, batch)

    content = path.read_text(encoding="utf-8")
    assert "batch_id,item_id,figi,ticker,status" in content
    assert "FIGI1,AAA,skipped,predicted_not_positive" in content
    assert str(path).startswith(str(csv_dir))


def test_random_bulk_start_guard_blocks_non_sandbox(monkeypatch):
    monkeypatch.setattr(random_bulk_trade_service.settings, "USE_SANDBOX", False)
    monkeypatch.setattr(random_bulk_trade_service.settings, "BULK_TRADE_WORKER_ENABLED", True)
    monkeypatch.setattr(random_bulk_trade_service.settings, "AUTO_SELL_DRY_RUN", False)

    try:
        random_bulk_trade_service.assert_random_bulk_start_allowed(has_tinkoff_token=True)
    except Exception as exc:
        assert getattr(exc, "status_code", None) == 403
        assert "sandbox" in str(exc.detail).lower()
    else:
        raise AssertionError("Expected guard to reject non-sandbox mode")


def test_auto_sell_batch_filter_closes_only_selected_batch(monkeypatch):
    db, _Session = make_session()
    now = datetime.now(timezone.utc)
    db.add_all([
        BulkTradeBatch(id=1, user_id=1, status="scheduled_sell"),
        BulkTradeBatch(id=2, user_id=1, status="scheduled_sell"),
        BotTrade(
            id=1,
            user_id=1,
            batch_id=1,
            figi="FIGI1",
            side="buy",
            quantity=1,
            price=Decimal("100"),
            amount=Decimal("100"),
            status="scheduled_sell",
            auto_sell_enabled=True,
            auto_sell_target_enabled=False,
            scheduled_sell_at=now - timedelta(minutes=1),
        ),
        BotTrade(
            id=2,
            user_id=1,
            batch_id=2,
            figi="FIGI2",
            side="buy",
            quantity=1,
            price=Decimal("100"),
            amount=Decimal("100"),
            status="scheduled_sell",
            auto_sell_enabled=True,
            auto_sell_target_enabled=False,
            scheduled_sell_at=now - timedelta(minutes=1),
        ),
    ])
    db.commit()

    monkeypatch.setattr(auto_sell_service, "get_current_price", lambda **_kwargs: 105.0)
    monkeypatch.setattr(auto_sell_service, "get_lot_size", lambda **_kwargs: 1)
    monkeypatch.setattr(auto_sell_service, "execute_order", lambda *args, **kwargs: {
        "status": "EXECUTED",
        "price": 105.0,
        "qty": 1,
        "amount": 105.0,
        "order_id": "sell-1",
    })
    monkeypatch.setattr(auto_sell_service.settings, "USE_SANDBOX", True)
    monkeypatch.setattr(auto_sell_service.settings, "AUTO_SELL_DRY_RUN", False)

    summary = auto_sell_service.process_due_auto_sells(db, user_id=1, batch_id=1)

    trade_one = db.query(BotTrade).filter(BotTrade.id == 1).first()
    trade_two = db.query(BotTrade).filter(BotTrade.id == 2).first()
    assert summary["closed"] == 1
    assert trade_one.status == "closed"
    assert trade_two.status == "scheduled_sell"


def test_bulk_worker_ignores_batch_until_scheduled_sell_is_due(monkeypatch):
    db, _Session = make_session()
    future = datetime.now(timezone.utc) + timedelta(minutes=30)
    batch = BulkTradeBatch(id=1, user_id=1, status="scheduled_sell", target_count=1)
    trade = BotTrade(
        id=1,
        user_id=1,
        batch_id=1,
        figi="FIGI1",
        side="buy",
        quantity=1,
        price=Decimal("100"),
        amount=Decimal("100"),
        status="scheduled_sell",
        auto_sell_enabled=True,
        auto_sell_target_enabled=False,
        scheduled_sell_at=future,
    )
    item = BulkTradeItem(
        batch_id=1,
        user_id=1,
        figi="FIGI1",
        status="bought",
        bot_trade_id=1,
        scheduled_sell_at=future,
    )
    db.add_all([batch, trade, item])
    db.commit()

    def fail_if_called(**_kwargs):
        raise AssertionError("Auto-sell should not run before scheduled_sell_at")

    monkeypatch.setattr(random_bulk_trade_service, "process_due_auto_sells", fail_if_called)

    summary = random_bulk_trade_service.process_due_bulk_batches(db)
    stored = db.query(BulkTradeBatch).filter(BulkTradeBatch.id == 1).first()

    assert summary == {"processed": 0, "completed": 0, "candidates": 0}
    assert stored.status == "scheduled_sell"
