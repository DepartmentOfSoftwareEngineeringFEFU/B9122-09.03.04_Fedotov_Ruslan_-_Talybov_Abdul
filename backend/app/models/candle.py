# candle.py
from sqlalchemy import Column, DateTime, Float, ForeignKey, Index, Integer, String, UniqueConstraint

from app.core.db import Base


class Candle(Base):
    __tablename__ = "candles"
    __table_args__ = (
        UniqueConstraint("user_id", "figi", "ts", name="uq_candles_user_figi_ts"),
        Index("ix_candles_user_figi_ts", "user_id", "figi", "ts"),
    )

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    figi = Column(String(32), index=True, nullable=False)
    ts = Column(DateTime, index=True, nullable=False)
    open = Column(Float)
    high = Column(Float)
    low = Column(Float)
    close = Column(Float)
    volume = Column(Float)
