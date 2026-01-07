from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, DateTime
from database import Base


class License(Base):
    __tablename__ = "licenses"

    id = Column(Integer, primary_key=True, index=True)
    license_key = Column(String, unique=True, index=True, nullable=False)
    max_devices = Column(Integer, default=1)
    active = Column(Boolean, default=True)
    expires_at = Column(DateTime, nullable=True)

    # JSON string: ["user1", "user2"]
    assigned_users = Column(String, nullable=True)


class Device(Base):
    __tablename__ = "devices"

    id = Column(Integer, primary_key=True, index=True)
    license_id = Column(Integer, ForeignKey("licenses.id"), nullable=False)
    device_id = Column(String, nullable=False)
