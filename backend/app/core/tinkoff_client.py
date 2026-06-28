# app/core/tinkoff_client.py
from __future__ import annotations

import logging
import warnings
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Iterable, List, Optional

# t-tech-investments 1.49.0 emits deprecated FIGI-field warnings while importing
# generated request defaults. Real broker calls below use instrument_id requests.
with warnings.catch_warnings():
    warnings.filterwarnings(
        "ignore",
        message=r".*\.figi is deprecated",
        category=DeprecationWarning,
    )
    from t_tech.invest import _grpc_helpers
    from t_tech.invest.grpc.common import InstrumentStatus, MoneyValue, PriceType
    from t_tech.invest.grpc.instruments import InstrumentIdType, InstrumentRequest, InstrumentsRequest
    from t_tech.invest.grpc.marketdata import CandleInterval, GetCandlesRequest, GetLastPricesRequest
    from t_tech.invest.grpc.operations import PortfolioRequest, PositionsRequest
    from t_tech.invest.grpc.orders import (
        GetOrderStateRequest,
        OrderDirection,
        OrderType,
        PostOrderRequest,
        TimeInForceType,
    )
    from t_tech.invest.grpc.sandbox import (
        CloseSandboxAccountRequest,
        OpenSandboxAccountRequest,
        SandboxPayInRequest,
    )
    from t_tech.invest.grpc.users import AccountType, GetAccountsRequest
    from t_tech.invest.grpc.utils.clients import Client

from app.core.config import settings
from app.core.crypto import decrypt_tinkoff_token
from app.core.db import SessionLocal
from app.models.user import User

logger = logging.getLogger(__name__)


POPULAR_MOEX_TICKERS = {
    "SBER", "LKOH", "GAZP", "GMKN", "ROSN", "NVTK", "PLZL", "PHOR", "NLMK", "CHMF",
    "MAGN", "TATN", "TATNP", "SNGS", "SNGSP", "SIBN", "MTSS", "AFLT", "ALRS", "MOEX",
    "VTBR", "IRAO", "FEES", "HYDR", "PIKK", "AFKS", "MGNT", "CBOM", "TRNFP", "RUAL",
}

_DEPRECATED_FIGI_PLACEHOLDER = _grpc_helpers.PLACEHOLDER


def _money_to_float(value: Any, default: float = 0.0) -> float:
    if value is None:
        return default
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, dict):
        units = value.get("units", 0)
        nano = value.get("nano", 0)
    else:
        units = getattr(value, "units", 0)
        nano = getattr(value, "nano", 0)
    try:
        return float(units) + float(nano) / 1_000_000_000
    except (TypeError, ValueError):
        return default


def _datetime_or_default(value: Optional[datetime], fallback: datetime) -> datetime:
    if value is None:
        return fallback
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _interval_from_value(value: str | CandleInterval | None) -> CandleInterval:
    if isinstance(value, CandleInterval):
        return value

    normalized = str(value or "1min").strip().lower()
    mapping = {
        "1min": CandleInterval.CANDLE_INTERVAL_1_MIN,
        "1m": CandleInterval.CANDLE_INTERVAL_1_MIN,
        "minute": CandleInterval.CANDLE_INTERVAL_1_MIN,
        "5min": getattr(CandleInterval, "CANDLE_INTERVAL_5_MIN", CandleInterval.CANDLE_INTERVAL_1_MIN),
        "5m": getattr(CandleInterval, "CANDLE_INTERVAL_5_MIN", CandleInterval.CANDLE_INTERVAL_1_MIN),
        "15min": getattr(CandleInterval, "CANDLE_INTERVAL_15_MIN", CandleInterval.CANDLE_INTERVAL_1_MIN),
        "15m": getattr(CandleInterval, "CANDLE_INTERVAL_15_MIN", CandleInterval.CANDLE_INTERVAL_1_MIN),
        "hour": getattr(CandleInterval, "CANDLE_INTERVAL_HOUR", CandleInterval.CANDLE_INTERVAL_1_MIN),
        "1h": getattr(CandleInterval, "CANDLE_INTERVAL_HOUR", CandleInterval.CANDLE_INTERVAL_1_MIN),
        "day": getattr(CandleInterval, "CANDLE_INTERVAL_DAY", CandleInterval.CANDLE_INTERVAL_1_MIN),
        "1d": getattr(CandleInterval, "CANDLE_INTERVAL_DAY", CandleInterval.CANDLE_INTERVAL_1_MIN),
    }
    return mapping.get(normalized, CandleInterval.CANDLE_INTERVAL_1_MIN)


def _enum_name(value: Any) -> str:
    enum_name = getattr(value, "name", None)
    if enum_name:
        return str(enum_name)
    return str(value or "")


def _order_direction(direction: str) -> OrderDirection:
    normalized = (direction or "").strip().lower()
    if normalized == "buy":
        return OrderDirection.ORDER_DIRECTION_BUY
    if normalized == "sell":
        return OrderDirection.ORDER_DIRECTION_SELL
    raise ValueError("direction must be 'buy' or 'sell'")


def validate_tinkoff_token(token: str, use_sandbox: bool) -> None:
    """Validate a T-Invest token without touching deprecated FIGI request fields."""
    with Client(token) as client:
        request = GetAccountsRequest()
        if use_sandbox:
            client.sandbox.get_sandbox_accounts(request)
        else:
            client.users.get_accounts(request)


class TinkoffClient:
    """Thin project wrapper around t-tech-investments.

    This class is the single integration point for market data, instruments,
    portfolio snapshots and order placement. It intentionally does not log user
    tokens, raw auth headers or full broker payloads.
    """

    def __init__(self, user_id: int | None = None):
        self.user_id = user_id
        if user_id:
            db = SessionLocal()
            try:
                user = db.query(User).filter(User.id == user_id).first()
                if not user:
                    raise ValueError(f"User {user_id} not found")
                if not user.tinkoff_token:
                    raise ValueError("Tinkoff token is required for this operation")
                self.token = decrypt_tinkoff_token(user.tinkoff_token)
                if not self.token:
                    raise ValueError("Tinkoff token is invalid or cannot be decrypted")
            finally:
                db.close()
        else:
            self.token = settings.TINKOFF_API_KEY

        self.use_sandbox = settings.USE_SANDBOX
        if not self.token:
            raise ValueError("Tinkoff token is required for this operation")

    def _get_account_id(self, client: Client) -> str:
        if self.use_sandbox:
            accounts_response = client.sandbox.get_sandbox_accounts(GetAccountsRequest())
            if not accounts_response.accounts:
                account = client.sandbox.open_sandbox_account(OpenSandboxAccountRequest())
                account_id = account.account_id
                logger.info("[SANDBOX] Created sandbox account for user_id=%s", self.user_id)
            else:
                account_id = accounts_response.accounts[0].id
            return account_id

        accounts = client.users.get_accounts(GetAccountsRequest()).accounts
        if not accounts:
            raise ValueError("No available T-Invest accounts")
        return accounts[0].id

    def resolve_account_id(self, account_id: str | None = None) -> str:
        """Return an explicit account id or the broker default used by orders."""
        normalized_account_id = (account_id or "").strip()
        if normalized_account_id:
            return normalized_account_id

        with Client(self.token) as client:
            return self._get_account_id(client)

    def get_accounts(self) -> List[dict]:
        """Return all available T-Invest accounts for the active token."""
        with Client(self.token) as client:
            request = GetAccountsRequest()
            response = (
                client.sandbox.get_sandbox_accounts(request)
                if self.use_sandbox
                else client.users.get_accounts(request)
            )
            accounts = []
            for account in response.accounts:
                opened_date = getattr(account, "opened_date", None)
                accounts.append({
                    "id": account.id,
                    "type": _enum_name(getattr(account, "type", "")),
                    "status": _enum_name(getattr(account, "status", "")),
                    "name": getattr(account, "name", ""),
                    "opened_date": opened_date.isoformat() if opened_date else None,
                    "sandbox": self.use_sandbox,
                })
            return accounts

    def open_account(self, account_type: AccountType = AccountType.ACCOUNT_TYPE_TINKOFF) -> str:
        """Open a sandbox account. Real accounts cannot be opened through API."""
        if not self.use_sandbox:
            raise ValueError("Opening accounts is available only in sandbox mode")

        with Client(self.token) as client:
            response = client.sandbox.open_sandbox_account(OpenSandboxAccountRequest())
            logger.info("[SANDBOX] Opened sandbox account for user_id=%s", self.user_id)
            return response.account_id

    def close_account(self, account_id: str) -> bool:
        """Close a sandbox account."""
        if not self.use_sandbox:
            raise ValueError("Closing accounts is available only in sandbox mode")

        with Client(self.token) as client:
            client.sandbox.close_sandbox_account(CloseSandboxAccountRequest(account_id=account_id))
            logger.info("[SANDBOX] Closed sandbox account for user_id=%s", self.user_id)
            return True

    def pay_in(self, account_id: str, amount: float, currency: str = "RUB") -> bool:
        """Pay in sandbox funds. Real account top-up is not supported here."""
        if not self.use_sandbox:
            raise ValueError("Pay-in is available only in sandbox mode")

        units = int(amount)
        nano = int(round((float(amount) - units) * 1_000_000_000))
        money = MoneyValue(currency=currency, units=units, nano=nano)

        with Client(self.token) as client:
            client.sandbox.sandbox_pay_in(SandboxPayInRequest(account_id=account_id, amount=money))
            logger.info("[SANDBOX] Paid in sandbox account for user_id=%s", self.user_id)
            return True

    def get_account_balance(self, account_id: str | None = None) -> dict:
        """Return portfolio and available cash summary."""
        with Client(self.token) as client:
            account_id = account_id or self._get_account_id(client)
            portfolio_request = PortfolioRequest(account_id=account_id)
            positions_request = PositionsRequest(account_id=account_id)
            portfolio = (
                client.sandbox.get_sandbox_portfolio(portfolio_request)
                if self.use_sandbox
                else client.operations.get_portfolio(portfolio_request)
            )
            positions = (
                client.sandbox.get_sandbox_positions(positions_request)
                if self.use_sandbox
                else client.operations.get_positions(positions_request)
            )

            cash_balance = 0.0
            for money in getattr(positions, "money", []) or []:
                if (getattr(money, "currency", "") or "").upper() == "RUB":
                    cash_balance += _money_to_float(money)

            total_amount = _money_to_float(getattr(portfolio, "total_amount_portfolio", None))
            if total_amount <= 0:
                total_amount = (
                    _money_to_float(getattr(portfolio, "total_amount_shares", None))
                    + _money_to_float(getattr(portfolio, "total_amount_bonds", None))
                    + _money_to_float(getattr(portfolio, "total_amount_etf", None))
                    + _money_to_float(getattr(portfolio, "total_amount_currencies", None))
                    + _money_to_float(getattr(portfolio, "total_amount_futures", None))
                    + _money_to_float(getattr(portfolio, "total_amount_options", None))
                )

            return {
                "account_id": account_id,
                "total_amount": total_amount,
                "available_amount": cash_balance,
                "currency": "RUB",
                "sandbox": self.use_sandbox,
            }

    def get_trading_mode(self) -> dict:
        return {
            "sandbox": self.use_sandbox,
            "mode": "sandbox" if self.use_sandbox else "real",
            "auto_sell_worker_enabled": bool(settings.AUTO_SELL_WORKER_ENABLED),
            "auto_sell_poll_seconds": int(settings.AUTO_SELL_POLL_SECONDS),
            "auto_sell_dry_run": bool(settings.AUTO_SELL_DRY_RUN),
            "bulk_trade_worker_enabled": bool(settings.BULK_TRADE_WORKER_ENABLED),
            "bulk_trade_worker_poll_seconds": int(settings.BULK_TRADE_WORKER_POLL_SECONDS),
            "real_trading_enabled": bool(settings.AI_BOT_REAL_TRADING_ENABLED),
        }

    def get_candles(
        self,
        figi: str,
        days: int = 5,
        interval: str | CandleInterval = "1min",
        from_: datetime | None = None,
        to: datetime | None = None,
    ):
        """Return candles for FIGI with configurable interval/time range."""
        to_dt = _datetime_or_default(to, datetime.now(timezone.utc))
        from_dt = _datetime_or_default(from_, to_dt - timedelta(days=max(1, int(days or 1))))

        with Client(self.token) as client:
            response = client.market_data.get_candles(
                GetCandlesRequest(
                    figi=_DEPRECATED_FIGI_PLACEHOLDER,
                    instrument_id=figi,
                    from_=from_dt,
                    to=to_dt,
                    interval=_interval_from_value(interval),
                )
            )
            return response.candles

    def get_current_prices(self, figi_list: Iterable[str]) -> List[dict]:
        """Return last prices for FIGIs in a stable project format."""
        figis = [str(figi).strip().upper() for figi in figi_list or [] if str(figi).strip()]
        if not figis:
            return []

        with Client(self.token) as client:
            prices_response = client.market_data.get_last_prices(
                GetLastPricesRequest(
                    figi=_DEPRECATED_FIGI_PLACEHOLDER,
                    instrument_id=figis,
                )
            )
            prices = []
            for price_data in getattr(prices_response, "last_prices", []):
                price_value = _money_to_float(getattr(price_data, "price", None))
                if price_value <= 0:
                    continue
                price_time = getattr(price_data, "time", None)
                prices.append({
                    "figi": getattr(price_data, "figi", None),
                    "price": price_value,
                    "time": price_time.isoformat() if price_time else None,
                })
            return prices

    def get_instrument_by_figi(self, figi: str) -> Dict[str, Any]:
        """Resolve a share instrument by FIGI through T-Invest instruments API."""
        normalized_figi = (figi or "").strip().upper()
        if not normalized_figi:
            raise ValueError("figi is required")
        if InstrumentIdType is None:
            raise ValueError("T-Invest SDK does not expose InstrumentIdType in this environment")

        with Client(self.token) as client:
            response = client.instruments.share_by(
                InstrumentRequest(
                    id_type=InstrumentIdType.INSTRUMENT_ID_TYPE_FIGI,
                    id=normalized_figi,
                )
            )
            instrument = getattr(response, "instrument", response)
            return self._instrument_to_dict(instrument)

    def get_popular_moex_shares(self, limit: int = 30) -> List[Dict[str, Any]]:
        """Return popular MOEX shares from the broker catalog when available."""
        limit = max(1, min(int(limit or 30), 100))
        with Client(self.token) as client:
            response = client.instruments.shares(
                InstrumentsRequest(instrument_status=InstrumentStatus.INSTRUMENT_STATUS_BASE)
            )
            instruments = getattr(response, "instruments", [])
            items = [
                self._instrument_to_dict(instrument)
                for instrument in instruments
                if self._is_popular_moex_share(instrument)
            ]
            items.sort(key=lambda item: item.get("ticker") or "")
            return items[:limit]

    def get_moex_shares(self, limit: int = 1000) -> List[Dict[str, Any]]:
        """Return the broker catalog of RUB MOEX shares for instrument pickers."""
        limit = max(1, min(int(limit or 1000), 1000))
        with Client(self.token) as client:
            response = client.instruments.shares(
                InstrumentsRequest(instrument_status=InstrumentStatus.INSTRUMENT_STATUS_BASE)
            )
            instruments = getattr(response, "instruments", [])
            items = [
                self._instrument_to_dict(instrument)
                for instrument in instruments
                if self._is_moex_rub_share(instrument)
            ]
            items.sort(key=lambda item: item.get("ticker") or "")
            return items[:limit]

    def place_order(self, figi: str, quantity: int, direction: str, account_id: str | None = None):
        """Place a market order. Callers must validate business rules before this."""
        if int(quantity or 0) <= 0:
            raise ValueError("quantity must be positive")

        with Client(self.token) as client:
            account_id = account_id or self._get_account_id(client)
            order_direction = _order_direction(direction)

            if self.use_sandbox:
                order = client.sandbox.post_sandbox_order(
                    PostOrderRequest(
                        figi=_DEPRECATED_FIGI_PLACEHOLDER,
                        instrument_id=figi,
                        quantity=int(quantity),
                        price=None,
                        direction=order_direction,
                        account_id=account_id,
                        order_type=OrderType.ORDER_TYPE_MARKET,
                        order_id="",
                        time_in_force=TimeInForceType.TIME_IN_FORCE_UNSPECIFIED,
                        price_type=PriceType.PRICE_TYPE_UNSPECIFIED,
                        confirm_margin_trade=False,
                    )
                )
            else:
                order = client.orders.post_order(
                    PostOrderRequest(
                        figi=_DEPRECATED_FIGI_PLACEHOLDER,
                        instrument_id=figi,
                        quantity=int(quantity),
                        price=None,
                        direction=order_direction,
                        account_id=account_id,
                        order_type=OrderType.ORDER_TYPE_MARKET,
                        order_id="",
                        time_in_force=TimeInForceType.TIME_IN_FORCE_UNSPECIFIED,
                        price_type=PriceType.PRICE_TYPE_UNSPECIFIED,
                        confirm_margin_trade=False,
                    )
                )

            logger.info(
                "T-Invest order placed user_id=%s figi=%s direction=%s qty=%s sandbox=%s",
                self.user_id,
                figi,
                direction,
                quantity,
                self.use_sandbox,
            )
            return order

    def get_order_state(self, order_id: str, account_id: str | None = None):
        """Return the final broker order state when available."""
        if not order_id:
            return None
        with Client(self.token) as client:
            account_id = account_id or self._get_account_id(client)
            request = GetOrderStateRequest(
                account_id=account_id,
                order_id=order_id,
                price_type=PriceType.PRICE_TYPE_UNSPECIFIED,
            )
            if self.use_sandbox:
                return client.sandbox.get_sandbox_order_state(request)
            return client.orders.get_order_state(request)

    def get_portfolio(self, account_id: str | None = None):
        """Return broker portfolio in the shape used by existing frontend/routes."""
        with Client(self.token) as client:
            account_id = account_id or self._get_account_id(client)
            request = PortfolioRequest(account_id=account_id)
            portfolio = (
                client.sandbox.get_sandbox_portfolio(request)
                if self.use_sandbox
                else client.operations.get_portfolio(request)
            )

            result: List[Dict[str, Any]] = []
            figis: List[str] = []
            for position in getattr(portfolio, "positions", []):
                figi = getattr(position, "figi", None)
                quantity_obj = getattr(position, "quantity", None) or getattr(position, "balance", None)
                balance_value = _money_to_float(quantity_obj)
                expected_yield = _money_to_float(getattr(position, "expected_yield", None))
                instrument_type = str(getattr(position, "instrument_type", "") or "").lower()
                currency = getattr(position, "currency", "RUB") or "RUB"

                if figi:
                    figis.append(figi)

                current_price = _money_to_float(getattr(position, "current_price", None), 0.0)
                result.append({
                    "figi": figi,
                    "ticker": getattr(position, "ticker", None),
                    "instrument_type": "currency" if "currency" in instrument_type else "share" if "share" in instrument_type else instrument_type,
                    "balance": balance_value,
                    "blocked": getattr(position, "blocked", False),
                    "lots": getattr(position, "lots", None),
                    "expected_yield": expected_yield,
                    "currency": currency,
                    "price": current_price if current_price > 0 else None,
                    "value": None,
                })

            prices = {item["figi"]: item["price"] for item in self.get_current_prices(figis) if item.get("figi")}
            total_value = 0.0
            cash_balance = 0.0

            for item in result:
                instrument_type = item.get("instrument_type")
                if instrument_type == "currency" and item.get("currency") == "RUB":
                    price = item.get("price") or 1.0
                    cash_balance += float(item.get("balance") or 0.0)
                else:
                    price = prices.get(item.get("figi"), item.get("price") or 0.0)

                value = float(item.get("balance") or 0.0) * float(price or 0.0)
                item["price"] = float(price or 0.0)
                item["value"] = value
                total_value += value

            summary = {
                "totalAmountPortfolio": total_value,
                "cash_balance": cash_balance,
                "account_id": account_id,
                "sandbox": self.use_sandbox,
            }
            return {"status": "success", "portfolio": result, "summary": summary}

    def _instrument_to_dict(self, instrument: Any) -> Dict[str, Any]:
        figi = getattr(instrument, "figi", None)
        return {
            "figi": figi,
            "ticker": getattr(instrument, "ticker", None),
            "name": getattr(instrument, "name", None),
            "currency": (getattr(instrument, "currency", None) or "RUB").upper(),
            "exchange": getattr(instrument, "exchange", None),
            "lot": getattr(instrument, "lot", None),
            "instrument_type": "share",
            "current_price": None,
        }

    def _is_popular_moex_share(self, instrument: Any) -> bool:
        ticker = str(getattr(instrument, "ticker", "") or "").upper()
        exchange = str(getattr(instrument, "exchange", "") or "").upper()
        currency = str(getattr(instrument, "currency", "") or "").upper()
        return ticker in POPULAR_MOEX_TICKERS and currency == "RUB" and ("MOEX" in exchange or exchange == "")

    def _is_moex_rub_share(self, instrument: Any) -> bool:
        figi = str(getattr(instrument, "figi", "") or "").strip()
        ticker = str(getattr(instrument, "ticker", "") or "").strip()
        exchange = str(getattr(instrument, "exchange", "") or "").upper()
        currency = str(getattr(instrument, "currency", "") or "").upper()
        api_available = getattr(instrument, "api_trade_available_flag", True)
        return bool(figi and ticker) and currency == "RUB" and ("MOEX" in exchange or exchange == "") and bool(api_available)
