from datetime import datetime

from app.api.routes_trade import format_portfolio
from app.models import backtest_result, bot_trade, ml_model, model_forecast, stock, training_session  # noqa: F401
from app.models.order import Order
from app.services import trade_service


class FakeResponse(dict):
    pass


class FakeClient:
    def __init__(self, user_id=None):
        self.user_id = user_id

    def resolve_account_id(self, account_id=None):
        return account_id or FakeSession.default_account_id

    def place_order(self, figi, quantity, direction, account_id=None):
        FakeSession.last_place_order_account_id = account_id
        return FakeResponse(FakeSession.next_response or {"status": "EXECUTED", "price": FakeSession.next_price, "order_id": "broker-1"})

    def get_order_state(self, order_id, account_id=None):
        FakeSession.last_order_state_account_id = account_id
        return FakeSession.next_order_state

    def get_current_prices(self, figi_list):
        return [{"figi": figi, "price": FakeSession.current_prices.get(figi, 0)} for figi in figi_list]

    def get_account_balance(self, account_id=None):
        return {"available_amount": FakeSession.cash_balance, "total_amount": FakeSession.total_amount}

    def get_portfolio(self, account_id=None):
        if FakeSession.broker_portfolio_error:
            raise RuntimeError("broker unavailable")
        return {
            "status": "success",
            "portfolio": FakeSession.broker_positions,
            "summary": {**FakeSession.broker_summary, "account_id": account_id},
        }


class FakeQuery:
    def __init__(self, rows):
        self.rows = rows

    def filter(self, *_args):
        for condition in _args:
            left_key = getattr(getattr(condition, "left", None), "key", None)
            right_value = getattr(getattr(condition, "right", None), "value", None)
            if left_key == "user_id":
                self.rows = [row for row in self.rows if row.user_id == right_value]
            elif left_key == "account_id":
                self.rows = [row for row in self.rows if row.account_id == right_value]
        return self

    def order_by(self, *_args):
        return self

    def all(self):
        return self.rows


class FakeSession:
    rows = []
    added = None
    next_price = 100.0
    next_response = None
    next_order_state = None
    current_prices = {}
    broker_positions = []
    broker_summary = {}
    broker_portfolio_error = False
    cash_balance = 0.0
    total_amount = 0.0
    default_account_id = "default-account"
    last_place_order_account_id = None
    last_order_state_account_id = None

    def query(self, _model):
        return FakeQuery(self.rows)

    def add(self, obj):
        self.added = obj
        FakeSession.added = obj

    def commit(self):
        pass

    def refresh(self, obj):
        obj.id = 123
        if obj.created_at is None:
            obj.created_at = datetime(2026, 1, 1)

    def rollback(self):
        pass

    def close(self):
        pass


def make_order(side, qty, price, user_id=1, figi="FIGI1", account_id=None):
    return Order(
        user_id=user_id,
        figi=figi,
        side=side,
        qty=qty,
        price=price,
        amount=qty * price,
        account_id=account_id,
        status="EXECUTED",
        created_at=datetime(2026, 1, 1),
    )


def patch_service(monkeypatch, rows=None, price=100.0):
    FakeSession.rows = rows or []
    FakeSession.added = None
    FakeSession.next_price = price
    FakeSession.next_response = None
    FakeSession.next_order_state = None
    FakeSession.current_prices = {}
    FakeSession.broker_positions = []
    FakeSession.broker_summary = {}
    FakeSession.broker_portfolio_error = False
    FakeSession.cash_balance = 0.0
    FakeSession.total_amount = 0.0
    FakeSession.default_account_id = "default-account"
    FakeSession.last_place_order_account_id = None
    FakeSession.last_order_state_account_id = None
    monkeypatch.setattr(trade_service, "TinkoffClient", FakeClient)
    monkeypatch.setattr(trade_service, "SessionLocal", FakeSession)


def test_execute_order_saves_enriched_buy_order(monkeypatch):
    patch_service(monkeypatch, price=100.0)

    result = trade_service.execute_order("figi1", "buy", 2, user_id=1, source="manual")

    assert result["order_id"] == 123
    assert result["amount"] == 200.0
    assert result["average_price_after"] == 100.0
    assert result["position_qty_after"] == 2
    assert result["cost_basis_after"] == 200.0
    assert FakeSession.added.source == "manual"


def test_execute_order_persists_selected_account_id(monkeypatch):
    patch_service(monkeypatch, price=100.0)

    result = trade_service.execute_order("figi1", "buy", 2, user_id=1, source="manual", account_id="acc-1")

    assert result["account_id"] == "acc-1"
    assert FakeSession.added.account_id == "acc-1"
    assert FakeSession.last_place_order_account_id == "acc-1"
    assert FakeSession.last_order_state_account_id == "acc-1"


def test_execute_order_resolves_and_persists_default_account_id(monkeypatch):
    patch_service(monkeypatch, price=100.0)
    FakeSession.default_account_id = "default-acc"

    result = trade_service.execute_order("figi1", "buy", 2, user_id=1, source="manual")

    assert result["account_id"] == "default-acc"
    assert FakeSession.added.account_id == "default-acc"
    assert FakeSession.last_place_order_account_id == "default-acc"


def test_execute_order_recalculates_weighted_average_on_second_buy(monkeypatch):
    patch_service(monkeypatch, rows=[make_order("buy", 1, 100.0, account_id="default-account")], price=130.0)

    result = trade_service.execute_order("FIGI1", "buy", 2, user_id=1, source="manual")

    assert result["position_qty_after"] == 3
    assert result["cost_basis_after"] == 360.0
    assert result["average_price_after"] == 120.0


def test_execute_order_divides_total_executed_price_when_broker_returns_order_sum(monkeypatch):
    patch_service(monkeypatch)
    FakeSession.next_response = {
        "status": "EXECUTED",
        "executed_order_price": 16130.0,
        "order_id": "broker-1",
    }
    FakeSession.current_prices = {"FIGI1": 322.6}

    result = trade_service.execute_order("FIGI1", "buy", 50, user_id=1, source="manual")

    assert result["price"] == 322.6
    assert result["amount"] == 16130.0
    assert result["average_price_after"] == 322.6
    assert result["cost_basis_after"] == 16130.0


def test_execute_order_saves_share_quantity_for_lotted_share(monkeypatch):
    patch_service(monkeypatch)
    FakeSession.next_order_state = {
        "status": "EXECUTED",
        "lots_executed": 20,
        "initial_security_price": {"currency": "rub", "units": "117", "nano": 90000000},
        "executed_order_price": {"currency": "rub", "units": "23418", "nano": 0},
    }
    FakeSession.next_response = {"status": "EXECUTED", "order_id": "broker-1"}
    FakeSession.current_prices = {"BBG004730RP0": 116.95}

    result = trade_service.execute_order("BBG004730RP0", "buy", 20, user_id=1, source="manual")

    assert result["qty"] == 200
    assert result["price"] == 117.09
    assert result["amount"] == 23418.0
    assert result["position_qty_after"] == 200
    assert result["average_price_after"] == 117.09
    assert result["cost_basis_after"] == 23418.0
    assert FakeSession.added.raw_response["execution"]["lot"] == 10
    assert FakeSession.added.raw_response["execution"]["lots"] == 20


def test_get_portfolio_values_lotted_position_by_share_quantity(monkeypatch):
    patch_service(monkeypatch, rows=[make_order("buy", 200, 117.09, figi="BBG004730RP0")])
    FakeSession.current_prices = {"BBG004730RP0": 116.95}
    FakeSession.total_amount = 200000.0

    raw = trade_service.get_portfolio(user_id=1)
    formatted = format_portfolio(raw, user_id=1)

    assert formatted["positions"][0]["quantity"] == 200
    assert formatted["positions"][0]["price"] == 116.95
    assert formatted["positions"][0]["value"] == 23390.0
    assert formatted["positions"][0]["average_price"] == 117.09
    assert formatted["positions"][0]["cost_basis"] == 23418.0


def test_get_portfolio_filters_local_orders_by_account_id(monkeypatch):
    patch_service(monkeypatch, rows=[
        make_order("buy", 10, 100.0, account_id="old-account"),
        make_order("buy", 5, 200.0, account_id=None),
    ])
    FakeSession.current_prices = {"FIGI1": 120.0}
    FakeSession.cash_balance = 100000.0
    FakeSession.total_amount = 100000.0

    raw = trade_service.get_portfolio(user_id=1, account_id="new-account")
    formatted = format_portfolio(raw, user_id=1)

    assert formatted["total_value"] == 100000.0
    assert formatted["cash_balance"] == 100000.0
    assert formatted["total_profit"] == 0.0
    assert formatted["positions_count"] == 0
    assert formatted["positions"] == []


def test_get_portfolio_ignores_legacy_order_when_broker_position_matches_account(monkeypatch):
    patch_service(monkeypatch, rows=[
        make_order("buy", 1000, 100.0, figi="BBG004730N88", account_id=None),
    ])
    FakeSession.broker_positions = [{
        "figi": "BBG004730N88",
        "ticker": "SBER",
        "instrument_type": "share",
        "balance": 1000,
        "price": 260.0,
        "value": 260000.0,
        "expected_yield": 10000.0,
        "currency": "RUB",
    }]
    FakeSession.total_amount = 260000.0

    raw = trade_service.get_portfolio(user_id=1, account_id="acc-1")
    formatted = format_portfolio(raw, user_id=1)

    assert formatted["positions_count"] == 1
    assert formatted["positions"][0]["figi"] == "BBG004730N88"
    assert formatted["positions"][0]["ticker"] == "SBER"
    assert formatted["positions"][0]["quantity"] == 1000
    assert formatted["positions"][0]["average_price"] == 250.0
    assert formatted["positions"][0]["cost_basis"] == 250000.0
    assert formatted["positions"][0]["value"] == 260000.0


def test_get_portfolio_does_not_create_scoped_position_from_legacy_order(monkeypatch):
    patch_service(monkeypatch, rows=[
        make_order("buy", 1, 10000.0, figi="BBG004731489", account_id=None),
        make_order("buy", 1000, 320.0, figi="BBG004730N88", account_id="acc-1"),
    ])
    FakeSession.current_prices = {"BBG004730N88": 321.0, "BBG004731489": 10000.0}
    FakeSession.broker_positions = [{
        "figi": "BBG004730N88",
        "ticker": "SBER",
        "instrument_type": "share",
        "balance": 1000,
        "price": 321.0,
        "value": 321000.0,
        "expected_yield": 1000.0,
        "currency": "RUB",
    }]
    FakeSession.total_amount = 1000000.0

    raw = trade_service.get_portfolio(user_id=1, account_id="acc-1")
    formatted = format_portfolio(raw, user_id=1)

    assert formatted["positions_count"] == 1
    assert [position["figi"] for position in formatted["positions"]] == ["BBG004730N88"]


def test_average_buy_price_ignores_legacy_orders_for_selected_account(monkeypatch):
    patch_service(monkeypatch, rows=[
        make_order("buy", 1000, 100.0, figi="BBG004730N88", account_id=None),
        make_order("buy", 1000, 320.0, figi="BBG004730N88", account_id="acc-1"),
    ])

    assert trade_service.get_average_buy_price(user_id=1, figi="BBG004730N88", account_id="acc-1") == 320.0


def test_get_portfolio_returns_error_when_selected_account_broker_portfolio_unavailable(monkeypatch):
    patch_service(monkeypatch, rows=[
        make_order("buy", 10, 100.0, account_id="acc-1"),
    ])
    FakeSession.broker_portfolio_error = True

    raw = trade_service.get_portfolio(user_id=1, account_id="acc-1")

    assert raw["status"] == "error"
    assert "Broker portfolio is unavailable" in raw["message"]


def test_execute_order_partial_sell_uses_weighted_average_cost_basis(monkeypatch):
    patch_service(monkeypatch, rows=[make_order("buy", 3, 100.0, account_id="default-account")], price=130.0)

    result = trade_service.execute_order("FIGI1", "sell", 1, user_id=1, source="manual")

    assert result["position_qty_after"] == 2
    assert result["cost_basis_after"] == 200.0
    assert result["average_price_after"] == 100.0
    assert result["realized_pnl"] == 30.0
    assert result["realized_pnl_percent"] == 30.0


def test_get_portfolio_builds_positions_from_orders_with_current_price(monkeypatch):
    patch_service(monkeypatch, rows=[make_order("buy", 2, 100.0)])
    FakeSession.current_prices = {"FIGI1": 125.0}
    FakeSession.cash_balance = 50.0

    raw = trade_service.get_portfolio(user_id=1)
    formatted = format_portfolio(raw, user_id=1)

    assert formatted["total_value"] == 300.0
    assert formatted["cash_balance"] == 50.0
    assert formatted["total_profit"] == 50.0
    assert formatted["positions_count"] == 1
    assert formatted["positions"][0]["price"] == 125.0
    assert formatted["positions"][0]["average_price"] == 100.0
    assert formatted["positions"][0]["cost_basis"] == 200.0
    assert formatted["positions"][0]["expected_yield"] == 50.0
    assert formatted["positions"][0]["price_status"] == "live"


def test_get_portfolio_normalizes_historical_total_price_with_current_price(monkeypatch):
    patch_service(monkeypatch, rows=[make_order("buy", 50, 16130.0)])
    FakeSession.current_prices = {"FIGI1": 322.6}
    FakeSession.total_amount = 20000.0

    raw = trade_service.get_portfolio(user_id=1)
    formatted = format_portfolio(raw, user_id=1)

    assert formatted["total_value"] == 20000.0
    assert formatted["cash_balance"] == 3870.0
    assert formatted["total_profit"] == 0.0
    assert formatted["positions"][0]["average_price"] == 322.6
    assert formatted["positions"][0]["cost_basis"] == 16130.0
