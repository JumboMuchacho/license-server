import os
from database import Base
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, func
try:
    TOKEN_PRICE = int(os.getenv("TOKEN_PRICE", "20"))
except ValueError:
    raise RuntimeError("TOKEN_PRICE must be a valid integer.")

class MpesaTransaction(Base):
    __tablename__ = "mpesa_transactions"
    id = Column(Integer, primary_key=True)
    device_id = Column(String, ForeignKey("devices.device_id"), index=True)
    checkout_request_id = Column(String, unique=True, index=True)
    mpesa_receipt_number = Column(String, nullable=True)
    phone_number = Column(String)
    amount = Column(Integer)
    tokens = Column(Integer)
    status = Column(String, default="PENDING")
    result_code = Column(Integer, nullable=True)
    result_desc = Column(String, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    completed_at = Column(DateTime, nullable=True)


def calculate_amount(tokens: int) -> int:
    return tokens * TOKEN_PRICE
