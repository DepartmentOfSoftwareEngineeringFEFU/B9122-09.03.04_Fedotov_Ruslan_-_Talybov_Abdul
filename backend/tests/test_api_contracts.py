from app.schemas.market import InstrumentResponse, PopularSharesResponse, TradingModeResponse
from app.schemas.model import AutoSellStatusResponse, ForecastRequest, RandomBulkBatchResponse, RandomBulkStartRequest, RecommendationResponse


def test_forecast_request_preserves_source_and_model_fields():
    request = ForecastRequest(figi="bbg004730n88", source="popular", horizon="1h", model_type="adaptive")

    assert request.figi == "bbg004730n88"
    assert request.source == "popular"
    assert request.hyperparam_mode == "auto"


def test_recommendation_contract_contains_confirmation_flags():
    recommendation = RecommendationResponse(
        action="BUY_OPTIONAL",
        reason_code="predicted_growth_without_position",
        message="Можно купить после подтверждения.",
        has_position=False,
        requires_confirmation=True,
    )

    assert recommendation.requires_confirmation is True
    assert recommendation.allow_auto_sell is False
    assert recommendation.recommended_quantity == 0


def test_market_contracts_are_flat_and_stable():
    popular = PopularSharesResponse(items=[{"figi": "BBG004730N88", "ticker": "SBER", "lot": 10, "lot_price": 3000.0}])
    instrument = InstrumentResponse(figi="BBG004730N88", ticker="SBER", current_price=300.0, lot=10, lot_price=3000.0)
    mode = TradingModeResponse(mode="sandbox", sandbox=True, auto_sell_worker_enabled=False, auto_sell_poll_seconds=60)

    assert popular.items[0].exchange == "MOEX"
    assert popular.items[0].lot == 10
    assert instrument.current_price == 300.0
    assert instrument.lot_price == 3000.0
    assert mode.real_trading_enabled is False
    assert mode.auto_sell_dry_run is True
    assert mode.bulk_trade_worker_enabled is False


def test_auto_sell_status_contract_defaults_real_trading_disabled():
    status = AutoSellStatusResponse(
        enabled=False,
        manual_process_enabled=False,
        poll_seconds=60,
        mode="sandbox",
    )

    assert status.real_trading_enabled is False
    assert status.due_count == 0


def test_random_bulk_contract_defaults_are_safe():
    request = RandomBulkStartRequest()
    response = RandomBulkBatchResponse(
        id=1,
        batch_id=1,
        user_id=1,
        status="queued",
        status_label="В очереди",
        next_action_label="Batch в очереди на запуск.",
        target_count=request.target_count,
        realized_pnl_total=0.0,
        realized_pnl_percent_total=None,
    )

    assert request.target_count == 30
    assert response.mode == "sandbox"
    assert response.csv_download_url is None
    assert response.status_label == "В очереди"
    assert response.next_action_label
    assert response.realized_pnl_total == 0.0
    assert response.items == []
