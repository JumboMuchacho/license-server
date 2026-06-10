from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship
from database import Base
from datetime import datetime


class License(Base):
    __tablename__ = "licenses"

    id = Column(Integer, primary_key=True)
    license_key = Column(String, unique=True, nullable=False)
    active = Column(Boolean, default=True)
    max_devices = Column(Integer, default=1)
    expires_at = Column(DateTime)
    assigned_users = Column(JSON, default=list)
    token_balance = Column(Integer, default=0)  # <-- Added token balance tracking

    devices = relationship(
        "Device",
        back_populates="license",
        cascade="all,delete"
    )


class Device(Base):
    __tablename__ = "devices"

    id = Column(Integer, primary_key=True)
    license_id = Column(Integer, ForeignKey("licenses.id"))
    device_id = Column(String)  # removed unique=True
    last_seen = Column(DateTime, default=datetime.utcnow)

    license = relationship("License", back_populates="devices")

class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True, index=True)
    device_id = Column(String, index=True)
    checkout_request_id = Column(String, unique=True, index=True)
    amount = Column(Integer)
    status = Column(String, default="PENDING") # PENDING, SUCCESS, FAILED
    created_at = Column(DateTime, default=func.now())
