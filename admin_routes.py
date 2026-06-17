from typing import List, Optional
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
import models
from pydantic import BaseModel

router = APIRouter(prefix="/admin/devices", tags=["Admin"])

class DeviceUpdate(BaseModel):
    active: Optional[bool] = None
    token_balance: Optional[int] = None

@router.get("")
def get_all_devices(db: Session = Depends(get_db)):
    """Fetch all devices and their status."""
    devices = db.query(models.Device).all()
    return [
        {
            "device_id": d.device_id,
            "active": d.active,
            "token_balance": d.token_balance,
            "last_seen": d.last_seen.isoformat() if d.last_seen else None
        } for d in devices
    ]

# Assuming you have a Pydantic model for this; if not, use a dict
@router.patch("/devices/{device_id}")
async def update_device_tokens(device_id: str, body: dict, db: Session = Depends(get_db), admin=Depends(verify_oauth)):
    device = db.query(models.Device).filter(models.Device.device_id == device_id).first()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")

    # Check if adjustment is provided (handles + and -)
    adjustment = body.get("token_adjustment", 0)

    # Calculate new balance, preventing it from going below zero
    new_balance = max(0, device.token_balance + adjustment)
    device.token_balance = new_balance

    db.commit()
    return {"new_balance": device.token_balance}

@router.delete("/{device_id}")
def delete_device(device_id: str, db: Session = Depends(get_db)):
    """Remove a device registration."""
    device = db.query(models.Device).filter(models.Device.device_id == device_id).first()
    if device:
        db.delete(device)
        db.commit()
    return {"status": "deleted"}


@router.get("/analytics")
async def get_analytics(db: Session = Depends(get_db)):
    # Calculate totals
    total_revenue = db.query(func.sum(MpesaTransaction.amount)).filter(MpesaTransaction.status == "SUCCESS").scalar() or 0
    total_txns = db.query(MpesaTransaction).count()
    success_rate = db.query(MpesaTransaction).filter(MpesaTransaction.status == "SUCCESS").count()

    return {
        "revenue": total_revenue,
        "total_txns": total_txns,
        "success_rate": success_rate
    }
