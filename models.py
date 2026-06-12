from sqlalchemy import Column, Integer, String, Boolean, DateTime
from database import Base
from datetime import datetime

class Device(Base):
    __tablename__ = "devices"

    id = Column(Integer, primary_key=True)

    device_id = Column(String, unique=True, index=True, nullable=False)

    token_balance = Column(Integer, default=0)
    active = Column(Boolean, default=True)

    last_seen = Column(DateTime, default=datetime.utcnow)
