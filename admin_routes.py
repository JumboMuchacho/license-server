import secrets
import json
from datetime import datetime, timedelta
from typing import List, Optional, Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, field_validator
from sqlalchemy.orm import Session

import models
from database import get_db
from auth import verify_oauth

router = APIRouter(prefix="/admin", tags=["admin"])


class LicenseCreate(BaseModel):
    max_devices: int = 1
    days: int = 30
    active: bool = True
    assigned_users: Optional[List[str]] = []


class LicenseOut(BaseModel):
    license_key: str
    active: bool
    max_devices: int
    expires_at: Optional[str] = None
    assigned_users: List[Any] = []

    @field_validator("assigned_users", mode="before")
    @classmethod
    def ensure_list(cls, v):
        if isinstance(v, str):
            try:
                return json.loads(v)
            except:
                return []
        return v if v is not None else []


def generate_license_key():
    return "-".join(secrets.token_hex(2).upper() for _ in range(5))


@router.get("/licenses", response_model=List[LicenseOut])
def list_licenses(
    user: dict = Depends(verify_oauth),
    db: Session = Depends(get_db),
):
    licenses = db.query(models.License).all()
    return [
        {
            "license_key": l.license_key,
            "active": l.active,
            "max_devices": l.max_devices,
            "expires_at": l.expires_at.isoformat() if l.expires_at else None,
            "assigned_users": l.assigned_users,
        }
        for l in licenses
    ]


@router.post("/licenses", response_model=LicenseOut)
def create_license(
    payload: LicenseCreate,
    user: dict = Depends(verify_oauth),
    db: Session = Depends(get_db),
):
    new_license = models.License(
        license_key=generate_license_key(),
        max_devices=payload.max_devices,
        active=payload.active,
        expires_at=datetime.utcnow() + timedelta(days=payload.days),
        assigned_users=payload.assigned_users,
    )

    db.add(new_license)
    db.commit()
    db.refresh(new_license)

    return {
        "license_key": new_license.license_key,
        "active": new_license.active,
        "max_devices": new_license.max_devices,
        "expires_at": new_license.expires_at.isoformat(),
        "assigned_users": new_license.assigned_users,
    }


@router.post("/licenses/{license_key}/revoke")
def revoke_license(
    license_key: str,
    user: dict = Depends(verify_oauth),
    db: Session = Depends(get_db),
):
    lic = db.query(models.License).filter_by(license_key=license_key).first()
    if not lic:
        raise HTTPException(404, "License not found")
    lic.active = False
    db.commit()
    return {"message": "License revoked"}


@router.post("/licenses/{license_key}/reactivate")
def reactivate_license(
    license_key: str,
    user: dict = Depends(verify_oauth),
    db: Session = Depends(get_db),
):
    lic = db.query(models.License).filter_by(license_key=license_key).first()
    if not lic:
        raise HTTPException(404, "License not found")
    lic.active = True
    db.commit()
    return {"message": "License reactivated"}


@router.delete("/licenses/{license_key}")
def delete_license(
    license_key: str,
    user: dict = Depends(verify_oauth),
    db: Session = Depends(get_db),
):
    lic = db.query(models.License).filter_by(license_key=license_key).first()
    if not lic:
        raise HTTPException(404, "License not found")
    db.delete(lic)
    db.commit()
    return {"message": "License deleted"}
