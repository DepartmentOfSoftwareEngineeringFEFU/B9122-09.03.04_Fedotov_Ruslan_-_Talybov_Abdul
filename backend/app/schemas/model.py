# app/schemas/routes_model.py
from pydantic import BaseModel, ConfigDict, Field
from typing import List, Optional, Dict, Any
from datetime import datetime


class MLModelBase(BaseModel):
    name: str
    description: Optional[str] = None
    model_type: str
    model_params: Dict[str, Any]
    feature_columns: List[str]
    target_column: str


class MLModelCreate(MLModelBase):
    user_id: int


class MLModelResponse(MLModelBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    training_metrics: Dict[str, Any]
    is_active: bool
    created_at: datetime


class TrainingSessionBase(BaseModel):
    name: str
    description: Optional[str] = None
    stock_id: int
    feature_columns: List[str]
    target_column: str
    train_start_date: Optional[datetime] = None
    train_end_date: Optional[datetime] = None


class TrainingSessionCreate(TrainingSessionBase):
    user_id: int


class TrainingSessionResponse(TrainingSessionBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    ml_model_id: Optional[int] = None
    train_samples: Optional[int] = None
    test_samples: Optional[int] = None
    training_time_seconds: Optional[float] = None
    created_at: datetime


class ForecastRequest(BaseModel):
    figi: str = Field(min_length=1, max_length=32)
    ticker: Optional[str] = Field(default=None, max_length=32)
    account_id: Optional[str] = Field(default=None, max_length=128)
    source: str = Field(default="manual", pattern="^(portfolio|popular|manual|bulk)$")
    horizon: str = Field(default="1h", pattern="^(1h|1d)$")
    model_type: str = Field(default="adaptive", pattern="^(svr|gpr|adaptive)$")
    hyperparam_mode: str = Field(default="auto", pattern="^(manual|auto)$")
    flat_threshold_percent: float = Field(default=1.0, ge=0.0, le=10.0)
    days: int = Field(default=7, ge=1, le=365)
    lags: int = Field(default=10, ge=1, le=120)
    svr_params: Optional[Dict[str, Any]] = None
    gpr_params: Optional[Dict[str, Any]] = None
    adaptive_params: Optional[Dict[str, Any]] = None


class RecommendationResponse(BaseModel):
    action: str
    reason_code: str
    message: str
    has_position: bool
    quantity: float = 0.0
    average_buy_price: float = 0.0
    cash_balance: float = 0.0
    expected_profit_from_avg: float = 0.0
    expected_profit_from_avg_percent: float = 0.0
    recommended_side: Optional[str] = None  # buy / sell / schedule_sell / none
    recommended_quantity: int = 0
    lot: int = 1
    lot_price: float = 0.0
    predicted_lot_price: float = 0.0
    estimated_trade_amount: float = 0.0
    max_affordable_quantity: int = 0
    requires_confirmation: bool = False
    allow_auto_sell: bool = False


class ForecastResponse(BaseModel):
    status: str
    forecast_id: Optional[int] = None
    figi: str
    ticker: Optional[str] = None
    account_id: Optional[str] = None
    source: Optional[str] = None
    horizon: str
    model_type: str
    model_type_effective: Optional[str] = None
    hyperparam_mode: str
    current_price: float
    predicted_price: float
    lot: int = 1
    lot_price: float = 0.0
    predicted_lot_price: float = 0.0
    price_delta: float
    price_delta_percent: float
    flat_threshold_percent: float
    metrics: Dict[str, Any]
    model_params: Dict[str, Any]
    recommendation: RecommendationResponse


class BotTradeConfirmRequest(BaseModel):
    forecast_id: int = Field(ge=1)
    side: Optional[str] = Field(default=None, pattern="^(buy|sell|schedule_sell)$")
    action: Optional[str] = Field(default=None, max_length=64)
    quantity: Optional[int] = Field(default=None, ge=1, le=1_000_000)
    auto_sell_enabled: bool = False
    auto_sell_target_enabled: bool = True
    scheduled_sell_at: Optional[datetime] = None
    sell_target_price: Optional[float] = Field(default=None, gt=0, le=10_000_000)
    idempotency_key: Optional[str] = Field(default=None, max_length=128)
    account_id: Optional[str] = Field(default=None, max_length=128)


class BotTradeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    forecast_id: Optional[int] = None
    figi: str
    ticker: Optional[str] = None
    instrument_name: Optional[str] = None
    side: str
    quantity: int
    price: float
    amount: float
    current_price: Optional[float] = None
    predicted_price: Optional[float] = None
    price_delta_percent: Optional[float] = None
    average_buy_price: Optional[float] = None
    cash_balance_at_signal: Optional[float] = None
    status: str
    source: str
    batch_id: Optional[int] = None
    account_id: Optional[str] = None
    recommendation_action: Optional[str] = None
    model_type_requested: Optional[str] = None
    model_type_used: Optional[str] = None
    order_id: Optional[str] = None
    broker_order_id: Optional[str] = None
    auto_sell_enabled: bool = False
    auto_sell_target_enabled: bool = True
    scheduled_sell_at: Optional[datetime] = None
    sell_target_price: Optional[float] = None
    realized_pnl: Optional[float] = None
    realized_pnl_percent: Optional[float] = None
    created_at: datetime
    confirmed_at: Optional[datetime] = None
    executed_at: Optional[datetime] = None
    closed_at: Optional[datetime] = None
    idempotency_key: Optional[str] = None


class BotTradeAnalyticsResponse(BaseModel):
    total_trades: int
    closed_trades: int
    open_trades: int
    scheduled_auto_sells: int = 0
    failed_trades: int = 0
    realized_pnl: float
    realized_pnl_percent: float
    win_rate: float
    avg_trade_return_percent: float
    best_trade_percent: float
    worst_trade_percent: float
    by_model: Dict[str, Dict[str, float]]


class AutoSellStatusResponse(BaseModel):
    enabled: bool
    manual_process_enabled: bool
    poll_seconds: int
    mode: str
    real_trading_enabled: bool = False
    dry_run: bool = True
    due_count: int = 0
    scheduled_count: int = 0


class AutoSellProcessResponse(BaseModel):
    status: str
    processed: int = 0
    closed: int = 0
    failed: int = 0
    skipped: int = 0
    candidates: int = 0
    detail: Optional[str] = None


class RandomBulkStartRequest(BaseModel):
    account_id: Optional[str] = Field(default=None, max_length=128)
    target_count: int = Field(default=30, ge=1, le=30)


class RandomBulkItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    batch_id: int
    figi: str
    ticker: Optional[str] = None
    status: str
    status_label: Optional[str] = None
    reason: Optional[str] = None
    reason_label: Optional[str] = None
    forecast_id: Optional[int] = None
    bot_trade_id: Optional[int] = None
    model_type_used: Optional[str] = None
    validation_mae: Optional[float] = None
    current_price: Optional[float] = None
    predicted_price: Optional[float] = None
    price_delta_percent: Optional[float] = None
    quantity: Optional[int] = None
    buy_price: Optional[float] = None
    buy_amount: Optional[float] = None
    scheduled_sell_at: Optional[datetime] = None
    closed_at: Optional[datetime] = None
    realized_pnl: Optional[float] = None
    realized_pnl_percent: Optional[float] = None
    error_message: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class RandomBulkBatchResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    batch_id: int
    user_id: int
    account_id: Optional[str] = None
    status: str
    status_label: Optional[str] = None
    next_action_label: Optional[str] = None
    target_count: int
    growth_threshold_percent: float = 0.0
    candidate_count: int = 0
    scanned_count: int = 0
    bought_count: int = 0
    skipped_count: int = 0
    failed_count: int = 0
    closed_count: int = 0
    mode: str = "sandbox"
    csv_download_url: Optional[str] = None
    nearest_scheduled_sell_at: Optional[datetime] = None
    realized_pnl_total: Optional[float] = None
    realized_pnl_percent_total: Optional[float] = None
    error_message: Optional[str] = None
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    items: List[RandomBulkItemResponse] = Field(default_factory=list)
