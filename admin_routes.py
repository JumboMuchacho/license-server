import secrets
import json
from datetime import datetime, timezone, timedelta
from typing import List, Optional, Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, field_validator
from sqlalchemy.orm import Session

import models
from database import get_db
from auth import verify_oauth

router = APIRouter(prefix="/admin", tags=["admin"])

# --- Schemas ---
class LicenseCreate(BaseModel):
    max_devices: int = 1
    days: int = 30
    active: bool = True
    assigned_users: Optional[List[str]] = []

class LicenseOut(BaseModel):
    license_key: str
    active: bool
    max_devices: int
    expires_at: Optional[str]
    assigned_users: List[Any] = []

    @field_validator("assigned_users", mode="before")
    @classmethod
    def ensure_list(cls, v):
        if isinstance(v, str):
            try: return json.loads(v)
            except: return []
        return v or []

# --- Helpers ---
def generate_license_key():
    return "-".join(secrets.token_hex(2).upper() for _ in range(5))

# --- Routes ---

@router.get("/licenses", response_model=List[LicenseOut])
def list_licenses(user=Depends(verify_oauth), db: Session = Depends(get_db)):
    licenses = db.query(models.License).all()
    # Explicitly ensure assigned_users is returned as a list for the UI dropdown
    return [
        {
            "license_key": l.license_key,
            "active": l.active,
            "max_devices": l.max_devices,
            "expires_at": l.expires_at.isoformat() if l.expires_at else None,
            "assigned_users": l.assigned_users if isinstance(l.assigned_users, list) else [],
        }
        for l in licenses
    ]

@router.post("/licenses", response_model=LicenseOut)
def create_license(payload: LicenseCreate, user=Depends(verify_oauth), db: Session = Depends(get_db)):
    now_utc = datetime.now(timezone.utc).replace(tzinfo=None)
    expiration = now_utc + timedelta(days=payload.days)

    lic = models.License(
        license_key=generate_license_key(),
        max_devices=payload.max_devices,
        active=payload.active,
        expires_at=expiration,
        assigned_users=payload.assigned_users,
    )
    db.add(lic)
    db.commit()
    db.refresh(lic)
    return {
        "license_key": lic.license_key,
        "active": lic.active,
        "max_devices": lic.max_devices,
        "expires_at": lic.expires_at.isoformat(),
        "assigned_users": lic.assigned_users,
    }

@router.post("/licenses/{key}/revoke")
def revoke_license(key: str, user=Depends(verify_oauth), db: Session = Depends(get_db)):
    lic = db.query(models.License).filter_by(license_key=key).first()
    if not lic: raise HTTPException(404, "License not found")
    lic.active = False
    db.commit()
    return {"status": "revoked"}

@router.post("/licenses/{key}/reactivate")
def reactivate_license(key: str, user=Depends(verify_oauth), db: Session = Depends(get_db)):
    lic = db.query(models.License).filter_by(license_key=key).first()
    if not lic: raise HTTPException(404, "License not found")
    lic.active = True
    db.commit()
    return {"status": "activated"}

@router.delete("/licenses/{key}")
def delete_license(key: str, user=Depends(verify_oauth), db: Session = Depends(get_db)):
    lic = db.query(models.License).filter_by(license_key=key).first()
    if not lic: raise HTTPException(404, "License not found")
    db.delete(lic)
    db.commit()
    return {"status": "deleted"}