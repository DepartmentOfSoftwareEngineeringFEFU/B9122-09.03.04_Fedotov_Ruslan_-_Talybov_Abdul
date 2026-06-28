from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.db import Base
from app.models import user  # noqa: F401
from app.models.user import User
from app.services import data_service


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
    return db


def money(value):
    units = int(value)
    nano = int(round((value - units) * 1_000_000_000))
    return SimpleNamespace(units=units, nano=nano)


def candle(ts, close=100.0):
    return SimpleNamespace(
        time=ts,
        open=money(close - 0.1),
        high=money(close + 0.2),
        low=money(close - 0.2),
        close=money(close),
        volume=1000,
    )


def test_fetch_raw_candles_chunked_splits_sorts_and_dedupes():
    class FakeClient:
        def __init__(self):
            self.calls = []

        def get_candles(self, figi, interval, from_, to):
            self.calls.append((figi, interval, from_, to))
            return [candle(to, 101.0), candle(from_, 100.0), candle(from_, 100.0)]

    client = FakeClient()

    result = data_service._fetch_raw_candles_chunked(client, "FIGI1", days=2, interval="1min")

    assert len(client.calls) > 1
    assert all(call[1] == "1min" for call in client.calls)
    assert all(call[3] - call[2] <= timedelta(hours=12, seconds=1) for call in client.calls)

    timestamps = [data_service._normalize_ts(item.time) for item in result]
    assert timestamps == sorted(timestamps)
    assert len(timestamps) == len(set(timestamps))


def test_load_candles_for_forecast_falls_back_to_5min(monkeypatch):
    db = make_session()
    start = datetime.now(timezone.utc) - timedelta(hours=12)
    raw_5min = [candle(start + timedelta(minutes=5 * i), 100.0 + i * 0.01) for i in range(40)]

    def fail_1min(*_args, **_kwargs):
        raise RuntimeError("30014 maximum request period")

    class FakeClient:
        def __init__(self, user_id):
            self.user_id = user_id

        def get_candles(self, figi, interval, from_, to):
            assert interval == "5min"
            return raw_5min

    monkeypatch.setattr(data_service, "fetch_and_store_candles", fail_1min)
    monkeypatch.setattr(data_service, "TinkoffClient", FakeClient)

    loaded = data_service.load_candles_for_forecast(
        db,
        figi="FIGI1",
        days=3,
        user_id=1,
        min_required_by_interval={"1min": 70, "5min": 30},
    )

    assert loaded.interval == "5min"
    assert loaded.source == "broker_fallback"
    assert len(loaded.candles) == 40
    assert [attempt["interval"] for attempt in loaded.attempts] == ["1min", "1min", "5min"]
