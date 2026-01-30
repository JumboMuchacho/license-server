from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship
from database import Base
import datetime

class License(Base):
    __tablename__ = "licenses"

    id = Column(Integer, primary_key=True)
    license_key = Column(String, unique=True, index=True, nullable=False)
    active = Column(Boolean, default=True)
    max_devices = Column(Integer, default=1)
    expires_at = Column(DateTime)
    
    # Stores users as a JSON list []
    assigned_users = Column(JSON, default=list)

    devices = relationship("Device", back_populates="license", cascade="all,delete")

class Device(Base):
    __tablename__ = "devices"

    id = Column(Integer, primary_key=True)
    license_id = Column(Integer, ForeignKey("licenses.id"), nullable=False)
    device_id = Column(String, nullable=False)
    last_seen = Column(DateTime, default=datetime.datetime.utcnow)

    license = relationship("License", back_populates="devices")