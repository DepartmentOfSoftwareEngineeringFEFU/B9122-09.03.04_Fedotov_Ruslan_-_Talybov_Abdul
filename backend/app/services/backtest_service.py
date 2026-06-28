# app/services/backtest_service.py
import logging
from typing import Any, Dict, List

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


class BacktestModelUnavailableError(RuntimeError):
    """Raised when a backtest cannot be run because no persisted model exists."""


def calculate_additional_metrics(trades: List[Dict], prices: List[float]) -> Dict[str, float]:
    """Calculate simple performance metrics for already deterministic trades."""
    if len(trades) < 2:
        return {"win_rate": 0.0, "sharpe_ratio": 0.0, "max_drawdown": 0.0}

    profitable_trades = 0
    returns = []
    for i in range(0, len(trades) - 1, 2):
        if trades[i].get("type") == "BUY" and trades[i + 1].get("type") == "SELL":
            buy_price = float(trades[i].get("price") or 0.0)
            sell_price = float(trades[i + 1].get("price") or 0.0)
            if buy_price <= 0:
                continue
            profit = sell_price - buy_price
            if profit > 0:
                profitable_trades += 1
            returns.append(profit / buy_price)

    win_rate = profitable_trades / max(1, len(trades) // 2)
    sharpe = float(np.mean(returns) / np.std(returns)) if returns and np.std(returns) > 0 else 0.0

    peak = prices[0] if prices else 0.0
    max_dd = 0.0
    for price in prices:
        price = float(price or 0.0)
        if price > peak:
            peak = price
        if peak > 0:
            max_dd = max(max_dd, (peak - price) / peak)

    return {"win_rate": win_rate, "sharpe_ratio": sharpe, "max_drawdown": max_dd}


def backtest(prices: list, predictions: list, threshold: float = 0.001, initial_balance: float = 1000.0):
    """Run a deterministic long-only strategy from explicit price predictions."""
    if not prices or not predictions:
        raise ValueError("prices and predictions are required")
    if len(prices) != len(predictions):
        raise ValueError("prices and predictions must have the same length")

    balance = float(initial_balance)
    position = 0.0
    trades = []

    for i, (price, predicted_price) in enumerate(zip(prices, predictions)):
        price = float(price or 0.0)
        predicted_price = float(predicted_price or 0.0)
        if price <= 0:
            continue
        if predicted_price > price * (1 + threshold) and position == 0:
            position = balance / price
            balance = 0.0
            trades.append({"type": "BUY", "price": price, "time": i})
        elif predicted_price < price * (1 - threshold) and position > 0:
            balance = position * price
            position = 0.0
            trades.append({"type": "SELL", "price": price, "time": i})

    if position > 0:
        balance = position * float(prices[-1])
        trades.append({"type": "SELL", "price": float(prices[-1]), "time": len(prices) - 1})

    roi = (balance - initial_balance) / initial_balance if initial_balance else 0.0
    total_trades = len([t for t in trades if t.get("type") == "BUY"])

    return {
        "roi": roi,
        "final_balance": balance,
        "total_trades": total_trades,
        "trades": trades,
        **calculate_additional_metrics(trades, [float(p or 0.0) for p in prices]),
    }


def run_backtest_with_model(
    model_type: str,
    model_params: Dict[str, Any],
    prices_dict: Dict[str, pd.DataFrame],
    features_dict: Dict[str, pd.DataFrame],
    threshold: float = 0.001,
    initial_balance: float = 1000.0,
) -> Dict[str, Any]:
    """Run backtest across multiple stocks using persisted model predictions.

    The previous implementation generated random predictions. That is unsafe for
    a financial UI, so this function now refuses to run unless a deterministic
    persisted prediction pipeline is present in model_params.
    """
    all_trades = []
    portfolio_value = float(initial_balance)
    active_symbols = [symbol for symbol in prices_dict if symbol in features_dict]
    if not active_symbols:
        raise ValueError("No valid symbols for backtest")

    per_symbol_balance = float(initial_balance) / len(active_symbols)
    for symbol in active_symbols:
        prices_df = prices_dict[symbol]
        features_df = features_dict[symbol]
        close_prices = prices_df["close"].tolist()
        predictions = generate_predictions(model_type, model_params, features_df)
        stock_result = backtest(close_prices, predictions, threshold, per_symbol_balance)
        all_trades.extend([{**trade, "symbol": symbol} for trade in stock_result["trades"]])
        portfolio_value += stock_result["final_balance"] - per_symbol_balance

    total_roi = (portfolio_value - initial_balance) / initial_balance if initial_balance else 0.0
    all_prices = [p for prices in prices_dict.values() for p in prices["close"].tolist()]
    return {
        "roi": total_roi,
        "final_balance": portfolio_value,
        "total_trades": len([t for t in all_trades if t.get("type") == "BUY"]),
        "trades": all_trades,
        **calculate_additional_metrics(all_trades, all_prices),
    }


def generate_predictions(model_type: str, model_params: Dict[str, Any], features_df: pd.DataFrame) -> List[float]:
    """Return deterministic predictions from explicitly persisted values only."""
    explicit_predictions = (model_params or {}).get("predictions")
    if explicit_predictions is None:
        raise BacktestModelUnavailableError(
            "Backtest is disabled until trained model artifacts/predictions are persisted. "
            "Random demo predictions were removed."
        )

    predictions = [float(value) for value in explicit_predictions]
    if len(predictions) != len(features_df):
        raise ValueError("Persisted predictions length does not match feature rows")
    return predictions
