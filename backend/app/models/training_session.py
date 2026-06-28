# app/models/training_session.py
from sqlalchemy import Column, Integer, String, JSON, DateTime, Float, ForeignKey, Text
from sqlalchemy.orm import relationship
from app.core.db import Base
from datetime import datetime


class TrainingSession(Base):
    __tablename__ = "training_sessions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    stock_id = Column(Integer, ForeignKey("stocks.id"), nullable=False)
    ml_model_id = Column(Integer, ForeignKey("ml_models.id"))

    # Training data
    name = Column(String(200), nullable=False)
    description = Column(Text)
    feature_columns = Column(JSON, nullable=False)
    target_column = Column(String(100), nullable=False)
    train_start_date = Column(DateTime)
    train_end_date = Column(DateTime)
    test_start_date = Column(DateTime)
    test_end_date = Column(DateTime)

    # Data statistics
    train_samples = Column(Integer)
    test_samples = Column(Integer)
    data_statistics = Column(JSON)  # Mean, std, etc.

    # Training metadata
    training_time_seconds = Column(Float)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="training_sessions")
    stock = relationship("Stock", back_populates="training_sessions")
    ml_model = relationship("MLModel", back_populates="training_session")

    def __repr__(self):
        return f"<TrainingSession(id={self.id}, name='{self.name}', stock_id={self.stock_id})>"