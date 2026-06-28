from app.services.recommendation_service import PortfolioPosition, build_trade_recommendation


def test_existing_position_predicted_drop_recommends_sell():
    result = build_trade_recommendation(
        price_delta_percent=-2.5,
        flat_threshold_percent=1.0,
        position=PortfolioPosition(has_position=True, quantity=7, average_buy_price=100.0, cash_balance=5000.0),
        current_price=98.0,
        predicted_price=95.0,
    )

    assert result["action"] == "SELL"
    assert result["recommended_side"] == "sell"
    assert result["recommended_quantity"] == 7
    assert result["requires_confirmation"] is True
    assert result["allow_auto_sell"] is False


def test_existing_position_growth_recommends_hold_and_optional_buy():
    result = build_trade_recommendation(
        price_delta_percent=2.0,
        flat_threshold_percent=1.0,
        position=PortfolioPosition(has_position=True, quantity=3, average_buy_price=100.0, cash_balance=450.0),
        current_price=110.0,
        predicted_price=115.0,
        lot=10,
    )

    assert result["action"] == "HOLD_AND_OPTIONAL_BUY"
    assert result["recommended_side"] == "buy"
    assert result["max_affordable_quantity"] == 0
    assert result["lot"] == 10
    assert result["lot_price"] == 1100.0
    assert result["requires_confirmation"] is True
    assert result["allow_auto_sell"] is True
    assert result["expected_profit_from_avg_percent"] == 15.0


def test_position_flat_price_recommends_hold_without_confirmation():
    result = build_trade_recommendation(
        price_delta_percent=0.3,
        flat_threshold_percent=1.0,
        position=PortfolioPosition(has_position=True, quantity=5, average_buy_price=100.0, cash_balance=1000.0),
        current_price=101.0,
        predicted_price=101.3,
    )

    assert result["action"] == "HOLD"
    assert result["requires_confirmation"] is False
    assert result["recommended_side"] is None


def test_no_position_drop_recommends_do_not_buy():
    result = build_trade_recommendation(
        price_delta_percent=-1.2,
        flat_threshold_percent=1.0,
        position=PortfolioPosition(has_position=False, quantity=0, average_buy_price=0.0, cash_balance=10_000.0),
        current_price=100.0,
        predicted_price=98.8,
    )

    assert result["action"] == "DO_NOT_BUY"
    assert result["requires_confirmation"] is False


def test_no_position_growth_recommends_buy_optional():
    result = build_trade_recommendation(
        price_delta_percent=1.5,
        flat_threshold_percent=1.0,
        position=PortfolioPosition(has_position=False, quantity=0, average_buy_price=0.0, cash_balance=2500.0),
        current_price=100.0,
        predicted_price=101.5,
        lot=10,
    )

    assert result["action"] == "BUY_OPTIONAL"
    assert result["recommended_side"] == "buy"
    assert result["recommended_quantity"] == 10
    assert result["max_affordable_quantity"] == 20
    assert result["estimated_trade_amount"] == 1000.0
    assert result["lot_price"] == 1000.0
    assert result["requires_confirmation"] is True


def test_no_position_flat_price_recommends_wait():
    result = build_trade_recommendation(
        price_delta_percent=0.2,
        flat_threshold_percent=1.0,
        position=PortfolioPosition(has_position=False, quantity=0, average_buy_price=0.0, cash_balance=250.0),
        current_price=100.0,
        predicted_price=100.2,
    )

    assert result["action"] == "WAIT"
    assert result["requires_confirmation"] is False
