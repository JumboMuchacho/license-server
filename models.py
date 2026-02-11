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

    devices = relationship("Device", back_populates="license", cascade="all,delete")


class Device(Base):
    __tablename__ = "devices"

    id = Column(Integer, primary_key=True)
    license_id = Column(Integer, ForeignKey("licenses.id"))
    device_id = Column(String, unique=True)
    last_seen = Column(DateTime, default=datetime.utcnow)

    license = relationship("License", back_populates="devices")


class UpdateManifest(Base):
    __tablename__ = "update_manifest"

    latest_version = Column(String, nullable=False, primary_key=True)
    min_required_version = Column(String, nullable=False)
    url = Column(String, nullable=False)
    sha256 = Column(String, nullable=False)
    mandatory = Column(Boolean, default=False)
    updated_at = Column(DateTime, default=datetime.utcnow)
