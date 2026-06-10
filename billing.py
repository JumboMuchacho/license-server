from database import Base
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, func
from sqlalchemy.orm import relationship

class MpesaTransaction(Base):
    __tablename__ = "mpesa_transactions"
    id = Column(Integer, primary_key=True)
    license_key = Column(String, ForeignKey("licenses.license_key"))
    checkout_request_id = Column(String, unique=True, index=True)
    mpesa_receipt_number = Column(String, nullable=True)
    phone_number = Column(String)
    amount = Column(Integer)
    status = Column(String, default="PENDING")
    created_at = Column(DateTime, server_default=func.now())
    completed_at = Column(DateTime, nullable=True)

    # Optional: link back to license
    license = relationship("License", backref="transactions")
