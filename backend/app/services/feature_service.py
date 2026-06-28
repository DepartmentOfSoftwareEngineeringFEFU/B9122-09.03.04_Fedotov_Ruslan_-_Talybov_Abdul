from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Sequence, Tuple

import numpy as np


HORIZON_TO_STEPS = {
    "1h": 60,
    "1d": 390,
}

INTERVAL_MINUTES = {
    "1min": 1,
    "1m": 1,
    "minute": 1,
    "5min": 5,
    "5m": 5,
}


@dataclass(frozen=True)
class FeatureBuildResult:
    X: np.ndarray
    y: np.ndarray
    next_features: np.ndarray
    feature_names: List[str]
    horizon_steps: int
    lags: int


def normalize_horizon(value: str) -> str:
    horizon = (value or "1h").strip().lower()
    if horizon not in HORIZON_TO_STEPS:
        raise ValueError("horizon must be one of: 1h, 1d")
    return horizon


def normalize_interval(value: str = "1min") -> str:
    normalized = (value or "1min").strip().lower()
    if normalized in {"1m", "minute"}:
        return "1min"
    if normalized == "5m":
        return "5min"
    if normalized not in {"1min", "5min"}:
        return "1min"
    return normalized


def horizon_to_steps(horizon: str, interval: str = "1min") -> int:
    normalized_horizon = normalize_horizon(horizon)
    normalized_interval = normalize_interval(interval)
    base_steps = HORIZON_TO_STEPS[normalized_horizon]
    minutes = INTERVAL_MINUTES.get(normalized_interval, 1)
    return max(1, int(round(base_steps / minutes)))


def _to_float(value, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _extract_close_volume(candles: Iterable) -> Tuple[np.ndarray, np.ndarray]:
    closes: List[float] = []
    volumes: List[float] = []

    for candle in candles:
        close_value = _to_float(getattr(candle, "close", None), np.nan)
        if not np.isfinite(close_value):
            continue
        closes.append(close_value)
        volumes.append(_to_float(getattr(candle, "volume", None), 0.0))

    return np.asarray(closes, dtype=float), np.asarray(volumes, dtype=float)


def minimum_required_samples(horizon: str, lags: int = 10, interval: str = "1min") -> int:
    normalized_lags = max(int(lags or 10), 2)
    return normalized_lags + horizon_to_steps(horizon, interval=interval) + 10


def validate_min_samples(candles: Sequence, model_type: str, horizon: str, lags: int = 10, interval: str = "1min") -> None:
    closes, _ = _extract_close_volume(candles)
    min_required = minimum_required_samples(horizon, lags, interval=interval)
    if len(closes) < min_required:
        raise ValueError(
            f"Недостаточно свечей для прогноза {normalize_horizon(horizon)}: "
            f"нужно минимум {min_required}, доступно {len(closes)}"
        )

    # GPR/adaptive should not be trained on tiny samples because the result is unstable.
    normalized_model = (model_type or "adaptive").strip().lower()
    if normalized_model in {"gpr", "adaptive"} and len(closes) < min_required + 20:
        raise ValueError(
            f"Недостаточно свечей для {normalized_model}: нужно минимум {min_required + 20}, доступно {len(closes)}"
        )


def _safe_return(current: float, previous: float) -> float:
    if previous == 0:
        return 0.0
    return (current - previous) / previous


def _window_mean(values: np.ndarray) -> float:
    return float(np.mean(values)) if len(values) else 0.0


def _window_std(values: np.ndarray) -> float:
    return float(np.std(values)) if len(values) else 0.0


def _row_features(closes: np.ndarray, volumes: np.ndarray, end_idx: int, lags: int) -> List[float]:
    close_window = closes[end_idx - lags:end_idx]
    volume_window = volumes[end_idx - lags:end_idx] if len(volumes) >= end_idx else np.zeros(lags)

    features: List[float] = []

    # Latest lag first: close_lag_1 is the previous close.
    for lag in range(1, lags + 1):
        features.append(float(closes[end_idx - lag]))

    for lag in range(1, lags + 1):
        previous_idx = end_idx - lag - 1
        previous = closes[previous_idx] if previous_idx >= 0 else closes[end_idx - lag]
        features.append(float(_safe_return(closes[end_idx - lag], previous)))

    features.extend([
        _window_mean(close_window[-5:]),
        _window_mean(close_window[-10:]),
        _window_std(close_window[-5:]),
        _window_std(close_window[-10:]),
    ])

    for lag in range(1, lags + 1):
        features.append(float(volume_window[-lag] if lag <= len(volume_window) else 0.0))

    return features


def _feature_names(lags: int) -> List[str]:
    names: List[str] = []
    names.extend([f"close_lag_{lag}" for lag in range(1, lags + 1)])
    names.extend([f"return_lag_{lag}" for lag in range(1, lags + 1)])
    names.extend(["rolling_mean_5", "rolling_mean_10", "rolling_std_5", "rolling_std_10"])
    names.extend([f"volume_lag_{lag}" for lag in range(1, lags + 1)])
    return names


def build_next_target(candles: Sequence, horizon: str, lags: int = 10, interval: str = "1min") -> np.ndarray:
    closes, volumes = _extract_close_volume(candles)
    normalized_lags = max(int(lags or 10), 2)
    if len(closes) < normalized_lags:
        raise ValueError("Недостаточно свечей для построения next_features")
    return np.asarray([_row_features(closes, volumes, len(closes), normalized_lags)], dtype=float)


def build_features_for_forecast(candles: Sequence, horizon: str, lags: int = 10, interval: str = "1min") -> FeatureBuildResult:
    normalized_horizon = normalize_horizon(horizon)
    normalized_lags = max(int(lags or 10), 2)
    normalized_interval = normalize_interval(interval)
    horizon_steps = horizon_to_steps(normalized_horizon, interval=normalized_interval)

    validate_min_samples(candles, model_type="svr", horizon=normalized_horizon, lags=normalized_lags, interval=normalized_interval)
    closes, volumes = _extract_close_volume(candles)

    X: List[List[float]] = []
    y: List[float] = []

    for idx in range(normalized_lags, len(closes) - horizon_steps):
        X.append(_row_features(closes, volumes, idx, normalized_lags))
        y.append(float(closes[idx + horizon_steps]))

    if not X:
        raise ValueError("Недостаточно свечей для выбранного горизонта и количества лагов")

    next_features = build_next_target(candles, horizon=normalized_horizon, lags=normalized_lags, interval=normalized_interval)
    return FeatureBuildResult(
        X=np.asarray(X, dtype=float),
        y=np.asarray(y, dtype=float),
        next_features=next_features,
        feature_names=_feature_names(normalized_lags),
        horizon_steps=horizon_steps,
        lags=normalized_lags,
    )
