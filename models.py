from sqlalchemy import Column, Integer, String, Boolean, ForeignKey
from database import Base

class License(Base):
    __tablename__ = "licenses"

    id = Column(Integer, primary_key=True)
    license_key = Column(String, unique=True, index=True)
    max_devices = Column(Integer, default=1)
    active = Column(Boolean, default=True)

class Device(Base):
    __tablename__ = "devices"

    id = Column(Integer, primary_key=True)
    license_id = Column(Integer, ForeignKey("licenses.id"))
    device_id = Column(String)
