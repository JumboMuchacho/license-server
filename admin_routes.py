from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from database import SessionLocal
import models, secrets, string, datetime

router = APIRouter()

# Dummy admin auth (replace with proper auth later)
def get_admin(token: str = Query(None)):
    if token != "SUPER_SECRET_ADMIN_TOKEN":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")
    return True

def generate_license_key(length=12):
    chars = string.ascii_uppercase + string.digits
    # create groups of 4 separated by dashes
    return '-'.join(''.join(secrets.choice(chars) for _ in range(4)) for _ in range(max(1, length // 4)))


@router.post("/admin/licenses")
def create_license(max_devices: int = 1, days: int = 365, active: bool = True, admin: bool = Depends(get_admin)):
    db: Session = SessionLocal()
    new_license = models.License(
        license_key=generate_license_key(),
        max_devices=max_devices,
        active=active,
        expires_at=datetime.datetime.utcnow() + datetime.timedelta(days=days)
    )
    db.add(new_license)
    db.commit()
    db.refresh(new_license)
    db.close()
    return {"license_key": new_license.license_key, "expires_at": new_license.expires_at}


@router.get("/admin/licenses")
def list_licenses(admin: bool = Depends(get_admin)):
    db: Session = SessionLocal()
    rows = db.query(models.License).order_by(models.License.id.desc()).all()
    result = []
    for r in rows:
        result.append({
            "license_key": r.license_key,
            "max_devices": r.max_devices,
            "active": bool(r.active),
            "expires_at": r.expires_at.isoformat() if r.expires_at else None
        })
    db.close()
    return result


@router.post("/admin/licenses/{license_key}/revoke")
def revoke_license(license_key: str, admin: bool = Depends(get_admin)):
    db: Session = SessionLocal()
    lic = db.query(models.License).filter_by(license_key=license_key).first()
    if not lic:
        db.close()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="License not found")
    lic.active = False
    db.commit()
    db.refresh(lic)
    db.close()
    return {"license_key": lic.license_key, "active": lic.active}


@router.post("/admin/licenses/{license_key}/reactivate")
def reactivate_license(license_key: str, admin: bool = Depends(get_admin)):
    db: Session = SessionLocal()
    lic = db.query(models.License).filter_by(license_key=license_key).first()
    if not lic:
        db.close()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="License not found")
    lic.active = True
    db.commit()
    db.refresh(lic)
    db.close()
    return {"license_key": lic.license_key, "active": lic.active}


@router.delete("/admin/licenses/{license_key}")
def delete_license(license_key: str, admin: bool = Depends(get_admin)):
    db: Session = SessionLocal()
    lic = db.query(models.License).filter_by(license_key=license_key).first()
    if not lic:
        db.close()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="License not found")
    # delete related devices first
    db.query(models.Device).filter_by(license_id=lic.id).delete()
    db.delete(lic)
    db.commit()
    db.close()
    return {"detail": "deleted"}
