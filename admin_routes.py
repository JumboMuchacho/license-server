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

@router.patch("/{device_id}")
def update_device(device_id: str, payload: DeviceUpdate, db: Session = Depends(get_db)):
    """Update device status or force token adjustments."""
    device = db.query(models.Device).filter(models.Device.device_id == device_id).first()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")

    if payload.active is not None:
        device.active = payload.active
    if payload.token_balance is not None:
        device.token_balance = payload.token_balance

    db.commit()
    return {"status": "success"}

@router.delete("/{device_id}")
def delete_device(device_id: str, db: Session = Depends(get_db)):
    """Remove a device registration."""
    device = db.query(models.Device).filter(models.Device.device_id == device_id).first()
    if device:
        db.delete(device)
        db.commit()
    return {"status": "deleted"}
