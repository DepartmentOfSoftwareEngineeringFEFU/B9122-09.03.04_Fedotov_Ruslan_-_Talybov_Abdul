from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, JSON, UniqueConstraint
from datetime import datetime
from app.core.db import Base

class Order(Base):
    __tablename__ = "orders"
    __table_args__ = (UniqueConstraint("user_id", "idempotency_key", name="uq_orders_user_idempotency_key"),)

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)
    figi = Column(String(32), index=True)
    side = Column(String(8))
    qty = Column(Integer)
    price = Column(Float)
    amount = Column(Float)
    average_price_after = Column(Float)
    position_qty_after = Column(Integer)
    cost_basis_after = Column(Float)
    realized_pnl = Column(Float)
    realized_pnl_percent = Column(Float)
    status = Column(String(32))
    broker_order_id = Column(String(128))
    account_id = Column(String(128))
    source = Column(String(64), default="manual")
    idempotency_key = Column(String(128), nullable=True)
    raw_response = Column(JSON)
    metrics_status = Column(String(32), default="calculated")
    created_at = Column(DateTime, default=datetime.utcnow)
