from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from fastapi.security import HTTPBasic, HTTPBasicCredentials
import os
from sqlalchemy.orm import Session
from database import SessionLocal
import models, secrets, string, datetime, json

router = APIRouter()

security = HTTPBasic()


def get_admin(credentials: HTTPBasicCredentials = Depends(security)):
    """Validate admin using HTTP Basic auth. Credentials are read from env vars:
    `ADMIN_USER` and `ADMIN_PASSWORD`. Defaults: admin / SUPER_SECRET_ADMIN_TOKEN
    """
    admin_user = os.getenv("ADMIN_USER", "admin")
    admin_pass = os.getenv("ADMIN_PASSWORD", "codecrazy")
    if not (secrets.compare_digest(credentials.username, admin_user) and secrets.compare_digest(credentials.password, admin_pass)):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")
    return True

def generate_license_key(length=12):
    chars = string.ascii_uppercase + string.digits
    # create groups of 4 separated by dashes
    return '-'.join(''.join(secrets.choice(chars) for _ in range(4)) for _ in range(max(1, length // 4)))


class LicenseCreate(BaseModel):
    max_devices: int = 1
    days: int = 365
    active: bool = True


@router.post("/admin/licenses")
def create_license(payload: LicenseCreate, admin: bool = Depends(get_admin)):
    # payload is parsed from JSON body — ensures `days` is read correctly
    db: Session = SessionLocal()
    new_license = models.License(
        license_key=generate_license_key(),
        max_devices=payload.max_devices,
        active=payload.active,
        expires_at=datetime.datetime.utcnow() + datetime.timedelta(days=payload.days)
    )
    db.add(new_license)
    db.commit()
    db.refresh(new_license)
    db.close()
    # present expires_at in YYYYMMDD (hh:mm AM/PM)
    formatted = None
    if new_license.expires_at:
        formatted = new_license.expires_at.strftime("%Y/%m/%d")
    return {"license_key": new_license.license_key, "expires_at": formatted}


@router.get("/admin/licenses")
def list_licenses(admin: bool = Depends(get_admin)):
    db: Session = SessionLocal()
    rows = db.query(models.License).order_by(models.License.id.desc()).all()
    result = []
    for r in rows:
        users = []
        if getattr(r, 'assigned_users', None):
            try:
                users = json.loads(r.assigned_users)
            except Exception:
                users = []
        result.append({
            "license_key": r.license_key,
            "max_devices": r.max_devices,
            "active": bool(r.active),
            "expires_at": (r.expires_at.strftime("%Y/%m/%d") if r.expires_at else None),
            "assigned_users": users
        })
    db.close()
    return result


@router.post('/admin/licenses/{license_key}/users')
def set_license_users(license_key: str, payload: dict, admin: bool = Depends(get_admin)):
    users = payload.get('users', []) if isinstance(payload, dict) else []
    db: Session = SessionLocal()
    lic = db.query(models.License).filter_by(license_key=license_key).first()
    if not lic:
        db.close()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='License not found')
    try:
        lic.assigned_users = json.dumps(users)
        db.commit()
        db.refresh(lic)
    finally:
        db.close()
    return { 'license_key': lic.license_key, 'users': users }


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
