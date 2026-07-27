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
    tokens = Column(Integer)
    status = Column(String, default="PENDING")
    result_code = Column(Integer, nullable=True)
    result_desc = Column(String, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    completed_at = Column(DateTime, nullable=True)


# Token package pricing (KES)
TOKEN_PRICES = {
    1: 40,
    2: 70,
    5: 160,
    10: 300,
    20: 600,
    40: 1200,
    80: 2400,
    160: 4400,
    320: 9000,
    640: 16000,
}


def calculate_amount(tokens: int) -> int:
    """
    Returns the purchase price for a token package.

    Raises:
        ValueError: If an unsupported token package is requested.
    """
    try:
        return TOKEN_PRICES[int(tokens)]
    except (KeyError, ValueError, TypeError):
        raise ValueError(f"Unsupported token package: {tokens}") from e
