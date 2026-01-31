import os
from typing import List, Optional
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Depends, HTTPException, status, Header
from sqlalchemy.orm import Session
from database import get_db
from models import License, Device
from pydantic import BaseModel

router = APIRouter(prefix="/admin/licenses", tags=["Admin"])

# --- SCHEMAS ---
class LicenseUpdate(BaseModel):
    active: Optional[bool] = None
    max_devices: Optional[int] = None
    assigned_users: Optional[List[str]] = None
    days: Optional[int] = None

class LicenseCreate(BaseModel):
    max_devices: int = 1
    days: int = 30
    assigned_users: List[str] = []

# --- ROUTES ---

@router.get("")
def get_all_licenses(db: Session = Depends(get_db)):
    """Fetches all licenses including nested device data and last seen timestamps."""
    licenses = db.query(License).all()
    results = []
    
    for lic in licenses:
        # Sort devices by last_seen so they appear consistently in UI slots
        sorted_devices = sorted(lic.devices, key=lambda x: x.last_seen if x.last_seen else datetime.min)
        
        results.append({
            "id": lic.id,
            "license_key": lic.license_key,
            "active": lic.active,
            "max_devices": lic.max_devices,
            "used_devices": len(lic.devices),
            "expires_at": lic.expires_at.isoformat() if lic.expires_at else None,
            "assigned_users": lic.assigned_users or [],
            "devices": [
                {
                    "device_id": d.device_id,
                    "last_seen": d.last_seen.isoformat() if d.last_seen else None
                } for d in sorted_devices
            ]
        })
    return results

@router.post("")
def create_license(payload: LicenseCreate, db: Session = Depends(get_db)):
    """Generates a new license key and saves it to the DB."""
    import uuid
    new_key = str(uuid.uuid4()).upper()
    expiry = datetime.now(timezone.utc) + timedelta(days=payload.days)
    
    new_lic = License(
        license_key=new_key,
        max_devices=payload.max_devices,
        expires_at=expiry,
        assigned_users=payload.assigned_users,
        active=True
    )
    db.add(new_lic)
    db.commit()
    db.refresh(new_lic)
    return new_lic

@router.patch("/{key}")
def update_license(key: str, payload: LicenseUpdate, db: Session = Depends(get_db)):
    """Updates license details (Active status, User IDs/Names, etc)."""
    lic = db.query(License).filter(License.license_key == key).first()
    if not lic:
        raise HTTPException(status_code=404, detail="License not found")
    
    if payload.active is not None:
        lic.active = payload.active
    if payload.assigned_users is not None:
        lic.assigned_users = payload.assigned_users
    if payload.max_devices is not None:
        lic.max_devices = payload.max_devices
    
    db.commit()
    return {"status": "success", "message": f"License {key} updated"}

@router.post("/{key}/revoke")
def revoke_license(key: str, db: Session = Depends(get_db)):
    lic = db.query(License).filter(License.license_key == key).first()
    if not lic: raise HTTPException(status_code=404)
    lic.active = False
    db.commit()
    return {"status": "revoked"}

@router.post("/{key}/reactivate")
def reactivate_license(key: str, db: Session = Depends(get_db)):
    lic = db.query(License).filter(License.license_key == key).first()
    if not lic: raise HTTPException(status_code=404)
    lic.active = True
    db.commit()
    return {"status": "activated"}

@router.delete("/{key}")
def delete_license(key: str, db: Session = Depends(get_db)):
    lic = db.query(License).filter(License.license_key == key).first()
    if not lic:
        raise HTTPException(status_code=404, detail="License not found")
    db.delete(lic)
    db.commit()
    return {"status": "deleted"}