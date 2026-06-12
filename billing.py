from database import Base
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, func

class MpesaTransaction(Base):
    __tablename__ = "mpesa_transactions"
    id = Column(Integer, primary_key=True)
    device_id = Column(String, ForeignKey("devices.device_id"), index=True)
    checkout_request_id = Column(String, unique=True, index=True)
    mpesa_receipt_number = Column(String, nullable=True)
    phone_number = Column(String)
    amount = Column(Integer)
    status = Column(String, default="PENDING")
    result_code = Column(Integer, nullable=True)
    result_desc = Column(String, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    completed_at = Column(DateTime, nullable=True)
