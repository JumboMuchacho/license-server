from sqlalchemy import (
    Column,
    Integer,
    String,
    Boolean,
    DateTime,
    ForeignKey,
    func,
)

from database import Base

class Device(Base):
    __tablename__ = "devices"

    id = Column(Integer, primary_key=True)

    device_id = Column(
        String,
        unique=True,
        index=True,
        nullable=False,
    )

    token_balance = Column(
        Integer,
        default=0,
    )

    active = Column(
        Boolean,
        default=True,
    )

    created_at = Column(
        DateTime,
        server_default=func.now(),
    )

    # Updated every heartbeat
    last_seen = Column(
        DateTime,
        nullable=True,
        index=True,
    )


class ConsumedToken(Base):
    __tablename__ = "consumed_tokens"

    id = Column(Integer, primary_key=True)

    # Website transaction/order ID (prevents consuming a token twice)
    txn_id = Column(String, unique=True, index=True, nullable=False)

    # Device that consumed the token
    device_id = Column(
        String,
        ForeignKey("devices.device_id"),
        nullable=False,
        index=True,
    )

    # Automatically set when the token is consumed
    created_at = Column(DateTime, server_default=func.now())
