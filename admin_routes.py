# server/admin_routes.py
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from typing import List
from auth import verify_oauth
import models
from database import get_db
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
import secrets

router = APIRouter(prefix="/admin", tags=["admin"])

# ------------------------------
# Pydantic Schemas
# ------------------------------
class LicenseCreate(BaseModel):
    max_devices: int = 1
    days: int = 30
    active: bool = True

class LicenseOut(BaseModel):
    license_key: str
    active: bool
    max_devices: int
    expires_at: str = None
    assigned_users: str = None

# ------------------------------
# Helper
# ------------------------------
def generate_license_key(length: int = 20):
    return "-".join(
        secrets.token_hex(2).upper() for _ in range(length // 4)
    )

# ------------------------------
# Endpoints
# ------------------------------
@router.get("/licenses", response_model=List[LicenseOut])
def list_licenses(user: dict = Depends(verify_oauth), db: Session = Depends(get_db)):
    """List all licenses."""
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
def create_license(payload: LicenseCreate, user: dict = Depends(verify_oauth), db: Session = Depends(get_db)):
    """Create a new license."""
    license_key = generate_license_key()
    expires_at = datetime.utcnow() + timedelta(days=payload.days)

    new_license = models.License(
        license_key=license_key,
        max_devices=payload.max_devices,
        active=payload.active,
        expires_at=expires_at,
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
def revoke_license(license_key: str, user: dict = Depends(verify_oauth), db: Session = Depends(get_db)):
    """Deactivate a license."""
    lic = db.query(models.License).filter_by(license_key=license_key).first()
    if not lic:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="License not found")
    lic.active = False
    db.commit()
    return {"message": f"License {license_key} revoked."}

@router.post("/licenses/{license_key}/reactivate")
def reactivate_license(license_key: str, user: dict = Depends(verify_oauth), db: Session = Depends(get_db)):
    """Reactivate a license."""
    lic = db.query(models.License).filter_by(license_key=license_key).first()
    if not lic:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="License not found")
    lic.active = True
    db.commit()
    return {"message": f"License {license_key} reactivated."}

@router.delete("/licenses/{license_key}")
def delete_license(license_key: str, user: dict = Depends(verify_oauth), db: Session = Depends(get_db)):
    """Delete a license."""
    lic = db.query(models.License).filter_by(license_key=license_key).first()
    if not lic:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="License not found")
    db.delete(lic)
    db.commit()
    return {"message": f"License {license_key} deleted."}
