from types import SimpleNamespace

from app.services.bot_analytics_service import calculate_bot_trade_analytics


class FakeQuery:
    def __init__(self, trades):
        self.trades = trades

    def filter(self, *args, **kwargs):
        return self

    def all(self):
        return self.trades


class FakeDB:
    def __init__(self, trades):
        self.trades = trades

    def query(self, _model):
        return FakeQuery(self.trades)


def trade(**overrides):
    defaults = {
        "user_id": 1,
        "status": "closed",
        "side": "sell",
        "auto_sell_enabled": False,
        "realized_pnl": 0.0,
        "realized_pnl_percent": None,
        "model_type_used": "svr",
        "model_type_requested": "svr",
        "account_id": None,
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def test_analytics_counts_only_bot_trade_rows_from_bot_trade_model_query():
    trades = [
        trade(realized_pnl=100.0, realized_pnl_percent=5.0, model_type_used="svr"),
        trade(realized_pnl=-50.0, realized_pnl_percent=-2.0, model_type_used="gpr"),
        trade(status="scheduled_sell", side="buy", auto_sell_enabled=True, model_type_used="adaptive"),
        trade(status="failed", side="buy", model_type_used="adaptive"),
    ]

    result = calculate_bot_trade_analytics(FakeDB(trades), user_id=1)

    assert result["total_trades"] == 4
    assert result["closed_trades"] == 2
    assert result["open_trades"] == 1
    assert result["scheduled_auto_sells"] == 1
    assert result["failed_trades"] == 1
    assert result["realized_pnl"] == 50.0
    assert result["win_rate"] == 50.0
    assert result["best_trade_percent"] == 5.0
    assert result["worst_trade_percent"] == -2.0
    assert result["by_model"]["svr"]["closed_trades"] == 1


def test_analytics_account_filter_excludes_legacy_and_other_accounts():
    trades = [
        trade(account_id=None, realized_pnl=-1000.0, realized_pnl_percent=-10.0, model_type_used="svr"),
        trade(account_id="old", status="failed", side="buy", model_type_used="adaptive"),
        trade(account_id="new", realized_pnl=150.0, realized_pnl_percent=3.0, model_type_used="gpr"),
    ]

    result = calculate_bot_trade_analytics(FakeDB(trades), user_id=1, account_id="new")

    assert result["total_trades"] == 1
    assert result["closed_trades"] == 1
    assert result["failed_trades"] == 0
    assert result["realized_pnl"] == 150.0
    assert result["win_rate"] == 100.0
    assert list(result["by_model"].keys()) == ["gpr"]
