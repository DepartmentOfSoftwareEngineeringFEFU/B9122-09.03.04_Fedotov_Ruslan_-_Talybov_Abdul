from app.services import instrument_service


def test_list_moex_shares_uses_broker_catalog(monkeypatch):
    seen = {}

    class FakeClient:
        def __init__(self, user_id):
            seen["user_id"] = user_id

        def get_moex_shares(self, limit):
            seen["limit"] = limit
            return [
                {"figi": "figi-gmkn", "ticker": "GMKN", "name": "Норникель", "currency": "rub", "exchange": "MOEX", "lot": 1},
                {"figi": "figi-sber", "ticker": "SBER", "name": "Сбер Банк", "currency": "rub", "exchange": "MOEX", "lot": 10},
            ]

    monkeypatch.setattr(instrument_service, "TinkoffClient", FakeClient)

    result = instrument_service.list_moex_shares(user_id=42, limit=500)

    assert seen == {"user_id": 42, "limit": 500}
    assert [item["ticker"] for item in result] == ["GMKN", "SBER"]
    assert result[0]["figi"] == "FIGI-GMKN"
    assert result[0]["currency"] == "RUB"


def test_list_moex_shares_falls_back_to_static_seed(monkeypatch):
    class FailingClient:
        def __init__(self, user_id):
            pass

        def get_moex_shares(self, limit):
            raise RuntimeError("broker unavailable")

    monkeypatch.setattr(instrument_service, "TinkoffClient", FailingClient)

    result = instrument_service.list_moex_shares(user_id=42, limit=2)

    assert len(result) == 2
    assert result[0]["ticker"] == "SBER"
    assert result[1]["ticker"] == "LKOH"
