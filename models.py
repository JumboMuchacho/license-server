from sqlalchemy import Column, Integer, String, Boolean, DateTime, func # Import func
from database import Base

class Device(Base):
    __tablename__ = "devices"

    id = Column(Integer, primary_key=True)
    device_id = Column(String, unique=True, index=True, nullable=False)
    token_balance = Column(Integer, default=0)
    active = Column(Boolean, default=True)

    # Use server_default=func.now() for database-generated timestamps
    last_seen = Column(DateTime, server_default=func.now(), onupdate=func.now())
