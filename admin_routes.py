from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
import secrets

from database import SessionLocal
import models

router = APIRouter(prefix="/admin", tags=["admin"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.post("/licenses")
def create_license(
    max_devices: int = 1,
    days: int = 30,
    active: bool = True,
    db: Session = Depends(get_db),
):
    license_key = secrets.token_hex(16)
    expires_at = datetime.utcnow() + timedelta(days=days)

    lic = models.License(
        license_key=license_key,
        max_devices=max_devices,
        active=active,
        expires_at=expires_at,
        assigned_users=None,
    )

    db.add(lic)
    db.commit()
    db.refresh(lic)

    return {
        "license_key": lic.license_key,
        "max_devices": lic.max_devices,
        "expires_at": lic.expires_at.isoformat(),
        "active": lic.active,
    }


@router.get("/licenses")
def list_licenses(db: Session = Depends(get_db)):
    licenses = db.query(models.License).all()
    return licenses
