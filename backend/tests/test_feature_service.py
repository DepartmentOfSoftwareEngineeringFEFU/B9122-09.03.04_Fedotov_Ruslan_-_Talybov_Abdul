from types import SimpleNamespace

import pytest

from app.services.feature_service import (
    build_features_for_forecast,
    horizon_to_steps,
    minimum_required_samples,
    normalize_horizon,
    validate_min_samples,
)


def make_candles(count):
    return [SimpleNamespace(close=100 + i * 0.1, volume=1000 + i) for i in range(count)]


def test_normalize_horizon_rejects_invalid_value():
    with pytest.raises(ValueError):
        normalize_horizon("2h")


def test_validate_min_samples_rejects_too_few_candles():
    candles = make_candles(20)
    with pytest.raises(ValueError, match="Недостаточно свечей"):
        validate_min_samples(candles, model_type="svr", horizon="1h", lags=10)


def test_build_features_for_forecast_returns_expected_feature_shape_for_hour():
    lags = 4
    candles = make_candles(minimum_required_samples("1h", lags) + 5)

    result = build_features_for_forecast(candles, horizon="1h", lags=lags)

    assert result.horizon_steps == 60
    assert result.lags == lags
    assert result.X.shape[1] == len(result.feature_names)
    assert result.next_features.shape == (1, len(result.feature_names))
    assert "close_lag_1" in result.feature_names
    assert "rolling_mean_10" in result.feature_names
    assert "volume_lag_4" in result.feature_names


def test_one_hour_horizon_uses_interval_specific_steps():
    assert horizon_to_steps("1h", interval="1min") == 60
    assert horizon_to_steps("1h", interval="5min") == 12
    assert minimum_required_samples("1h", lags=4, interval="5min") == 26

    candles = make_candles(minimum_required_samples("1h", 4, interval="5min") + 5)
    result = build_features_for_forecast(candles, horizon="1h", lags=4, interval="5min")

    assert result.horizon_steps == 12
    assert result.X.shape[1] == len(result.feature_names)
