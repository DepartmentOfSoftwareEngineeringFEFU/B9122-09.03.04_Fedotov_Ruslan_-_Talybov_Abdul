# app/models/ml_model.py
from sqlalchemy import Column, Integer, String, JSON, DateTime, Text, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from app.core.db import Base
from datetime import datetime


class MLModel(Base):
    __tablename__ = "ml_models"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    name = Column(String(200), nullable=False)
    description = Column(Text)
    model_type = Column(String(50), nullable=False)  # SVR, GPR, etc.
    model_params = Column(JSON, nullable=False)
    training_metrics = Column(JSON, nullable=False)
    feature_columns = Column(JSON)  # List of feature columns used
    target_column = Column(String(100))  # Target variable
    model_size_bytes = Column(Integer)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="ml_models")
    backtest_results = relationship("BacktestResult", back_populates="ml_model")
    training_session = relationship("TrainingSession", back_populates="ml_model", uselist=False)

    def __repr__(self):
        return f"<MLModel(id={self.id}, name='{self.name}', type='{self.model_type}')>"