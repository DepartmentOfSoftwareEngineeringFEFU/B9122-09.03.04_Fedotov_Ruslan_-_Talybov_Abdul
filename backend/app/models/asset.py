from sqlalchemy import Column, Integer, String
from app.core.db import Base

class Asset(Base):
    __tablename__ = "assets"
    id = Column(Integer, primary_key=True, index=True)
    figi = Column(String(32), unique=True, index=True)
    ticker = Column(String(16))
    name = Column(String(128))
