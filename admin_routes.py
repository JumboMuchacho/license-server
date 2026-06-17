from typing import List, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
from database import get_db
import models
from billing import MpesaTransaction
from pydantic import BaseModel
from security import verify_oauth  # Import the fix

router = APIRouter(prefix="/admin/devices", tags=["Admin"])

class DeviceUpdate(BaseModel):
    active: Optional[bool] = None
    token_balance: Optional[int] = None

@router.get("")
def get_all_devices(db: Session = Depends(get_db)):
    devices = db.query(models.Device).all()
    return [
        {
            "device_id": d.device_id,
            "active": d.active,
            "token_balance": d.token_balance,
            "created_at": d.created_at.isoformat() if hasattr(d, 'created_at') and d.created_at else None
        } for d in devices
    ]

@router.patch("/{device_id}")
async def update_device_tokens(device_id: str, body: dict, db: Session = Depends(get_db), admin=Depends(verify_oauth)):
    device = db.query(models.Device).filter(models.Device.device_id == device_id).first()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")

    adjustment = body.get("token_adjustment", 0)
    device.token_balance = max(0, device.token_balance + adjustment)
    db.commit()
    return {"new_balance": device.token_balance}

@router.delete("/{device_id}")
def delete_device(device_id: str, db: Session = Depends(get_db), admin=Depends(verify_oauth)):
    device = db.query(models.Device).filter(models.Device.device_id == device_id).first()
    if device:
        db.delete(device)
        db.commit()
    return {"status": "deleted"}

@router.get("/analytics")
async def get_analytics(db: Session = Depends(get_db), admin=Depends(verify_oauth)):
    # Ensure MpesaTransaction is imported from models
    total_revenue = db.query(func.sum(models.MpesaTransaction.amount)).filter(models.MpesaTransaction.status == "SUCCESS").scalar() or 0
    total_txns = db.query(models.MpesaTransaction).count()
    success_rate = db.query(models.MpesaTransaction).filter(models.MpesaTransaction.status == "SUCCESS").count()

    growth = db.query(
        func.date(models.Device.created_at).label("date"),
        func.count(models.Device.id).label("count")
    ).group_by(func.date(models.Device.created_at)).order_by(func.date(models.Device.created_at)).all()

    return {
        "revenue": total_revenue,
        "total_txns": total_txns,
        "success_rate": success_rate,
        "growth_data": {
            "labels": [str(g.date) for g in growth],
            "values": [g.count for g in growth]
        }
    }
