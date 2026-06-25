from typing import List, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
from database import get_db
import models
from billing import MpesaTransaction
from pydantic import BaseModel
from auth import verify_oauth

class DeviceUpdate(BaseModel):
    active: Optional[bool] = None
    token_adjustment: Optional[int] = None

@router.get("/devices")
def get_all_devices(db: Session = Depends(get_db), admin=Depends(verify_oauth)):
    devices = db.query(models.Device).all()
    return [
        {
            "device_id": d.device_id,
            "active": d.active,
            "token_balance": d.token_balance,
            "created_at": d.created_at.isoformat() if hasattr(d, 'created_at') and d.created_at else None
        } for d in devices
    ]

@router.patch("/devices/{device_id}")
async def update_device_tokens(device_id: str, body: DeviceUpdate, db: Session = Depends(get_db), admin=Depends(verify_oauth)):
    device = db.query(models.Device).filter(models.Device.device_id == device_id).first()
    if not device:
        raise HTTPException(status_code=404, detail="Device tracking record completely missing.")

    # Access fields as attributes, not dictionary keys
    if body.token_adjustment is not None:
        device.token_balance = max(0, device.token_balance + body.token_adjustment)

    if body.active is not None:
        device.active = body.active

    db.commit()
    return {"success": True, "token_balance": device.token_balance, "active": device.active}

@router.delete("/devices/{device_id}")
async def delete_device(device_id: str, db: Session = Depends(get_db), admin=Depends(verify_oauth)):
    device = db.query(models.Device).filter(models.Device.device_id == device_id).first()
    if not device:
        raise HTTPException(status_code=404, detail="Target device not found in registry.")
    db.delete(device)
    db.commit()
    return {"success": True}

@router.get("/analytics")
def get_analytics(db: Session = Depends(get_db), admin=Depends(verify_oauth)):
    total_revenue = db.query(func.sum(MpesaTransaction.amount)).filter(MpesaTransaction.status == "SUCCESS").scalar() or 0
    total_txns = db.query(MpesaTransaction).count()
    success_rate = db.query(MpesaTransaction).filter(MpesaTransaction.status == "SUCCESS").count()

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

@router.post("/reset-analytics")
async def reset_analytics(db: Session = Depends(get_db), admin=Depends(verify_oauth)):
    try:
        db.query(MpesaTransaction).delete()
        db.commit()
        return {"success": True, "message": "All analytics logs successfully cleared."}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
