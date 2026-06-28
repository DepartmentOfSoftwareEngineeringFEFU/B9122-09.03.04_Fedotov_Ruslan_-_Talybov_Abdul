from sqlalchemy import Column, Integer, String, Enum, DECIMAL, DateTime, ForeignKey
from sqlalchemy.sql import func
from app.core.db import Base

class Trade(Base):
    __tablename__ = "trades"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    figi = Column(String(32), nullable=False)
    side = Column(String(10), nullable=False)  # buy / sell
    quantity = Column(Integer, nullable=False)
    price = Column(DECIMAL(12, 4), nullable=False)
    amount = Column(DECIMAL(15, 4), nullable=False)
    status = Column(String(50), default="completed")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
