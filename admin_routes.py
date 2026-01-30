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
    expires_at: Optional[str]
    assigned_users: List[Any] = []

    @field_validator("assigned_users", mode="before")
    @classmethod
    def ensure_list(cls, v):
        if isinstance(v, str):
            try:
                return json.loads(v)
            except:
                return []
        return v or []


def generate_license_key():
    return "-".join(secrets.token_hex(2).upper() for _ in range(5))


@router.get("/licenses", response_model=List[LicenseOut])
def list_licenses(
    user=Depends(verify_oauth),
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
    user=Depends(verify_oauth),
    db: Session = Depends(get_db),
):
    lic = models.License(
        license_key=generate_license_key(),
        max_devices=payload.max_devices,
        active=payload.active,
        expires_at=datetime.utcnow() + timedelta(days=payload.days),
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
