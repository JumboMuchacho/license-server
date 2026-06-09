import uuid
from typing import List, Optional
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
from models import License, Device
from pydantic import BaseModel

router = APIRouter(prefix="/admin/licenses", tags=["Admin"])

class LicenseUpdate(BaseModel):
    active: Optional[bool] = None
    assigned_users: Optional[List[str]] = None

class LicenseCreate(BaseModel):
    max_devices: int = 1
    days: int = 30
    assigned_users: List[str] = []

def generate_dashed_key():
    uid = uuid.uuid4().hex.upper()
    return f"{uid[:4]}-{uid[4:8]}-{uid[8:12]}-{uid[12:16]}"

@router.get("")
def get_all_licenses(db: Session = Depends(get_db)):
    licenses = db.query(License).all()
    results = []
    for lic in licenses:
        # Sort devices by last_seen
        device_list = sorted(lic.devices, key=lambda x: x.last_seen if x.last_seen else datetime.min)

        results.append({
            "license_key": lic.license_key,
            "active": lic.active,
            "max_devices": lic.max_devices,
            "used_devices": len(lic.devices),
            "token_balance": lic.token_balance,  # Integrated successfully
            "expires_at": lic.expires_at.isoformat() if lic.expires_at else None,
            "assigned_users": lic.assigned_users or [],
            "devices": [{"last_seen": d.last_seen.isoformat() if d.last_seen else None} for d in device_list]
        })
    return results

@router.post("")
def create_license(payload: LicenseCreate, db: Session = Depends(get_db)):
    new_key = generate_dashed_key()
    expiry = datetime.now(timezone.utc) + timedelta(days=payload.days)
    new_lic = License(
        license_key=new_key,
        max_devices=payload.max_devices,
        expires_at=expiry,
        assigned_users=payload.assigned_users,
        token_balance=0, # Initialize new licenses with 0 tokens
        active=True
    )
    db.add(new_lic)
    db.commit()
    db.refresh(new_lic)
    return new_lic

@router.patch("/{key}")
def update_license(key: str, payload: LicenseUpdate, db: Session = Depends(get_db)):
    lic = db.query(License).filter(License.license_key == key).first()
    if not lic: raise HTTPException(status_code=404)
    if payload.assigned_users is not None:
        lic.assigned_users = payload.assigned_users
    db.commit()
    return {"status": "success"}

@router.post("/{key}/revoke")
def revoke_license(key: str, db: Session = Depends(get_db)):
    lic = db.query(License).filter(License.license_key == key).first()
    if lic: lic.active = False; db.commit()
    return {"status": "revoked"}

@router.post("/{key}/reactivate")
def reactivate_license(key: str, db: Session = Depends(get_db)):
    lic = db.query(License).filter(License.license_key == key).first()
    if lic: lic.active = True; db.commit()
    return {"status": "activated"}

@router.delete("/{key}")
def delete_license(key: str, db: Session = Depends(get_db)):
    lic = db.query(License).filter(License.license_key == key).first()
    if lic: db.delete(lic); db.commit()
    return {"status": "deleted"}
