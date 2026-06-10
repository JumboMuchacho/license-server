from database import Base
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey

class MpesaTransaction(Base):
    __tablename__ = "mpesa_transactions"

    id = Column(Integer, primary_key=True)

    license_key = Column(String, ForeignKey("licenses.license_key"))

    checkout_request_id = Column(String, unique=True)
    mpesa_receipt_number = Column(String)

    phone_number = Column(String)
    amount = Column(Integer)

    status = Column(String, default="PENDING")

    created_at = Column(DateTime)
    completed_at = Column(DateTime)
