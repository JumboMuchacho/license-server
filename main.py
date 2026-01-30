from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import create_engine, Column, Integer, String, Boolean
from sqlalchemy.orm import sessionmaker, declarative_base, Session
from datetime import datetime, timedelta
import os, json, hmac, hashlib

DATABASE_URL = os.environ["DATABASE_URL"]
ADMIN_TOKEN = os.environ["ADMIN_TOKEN"]
LICENSE_SECRET = os.environ["LICENSE_SECRET"]

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()

app = FastAPI()

# --------------------
# Models
# --------------------
class License(Base):
    __tablename__ = "licenses"

    id = Column(Integer, primary_key=True)
    license_key = Column(String, unique=True, nullable=False)
    max_devices = Column(Integer, default=1)
    expires_at = Column(Integer)
    active = Column(Boolean, default=True)
    devices = Column(String, default="[]")

Base.metadata.create_all(engine)

# --------------------
# Utils
# --------------------
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()

def admin_auth(req: Request):
    token = req.headers.get("Authorization", "").replace("Bearer ", "")
    if token != ADMIN_TOKEN:
        raise HTTPException(401, "Unauthorized")

def sign(payload: dict):
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    sig = hmac.new(LICENSE_SECRET.encode(), raw, hashlib.sha256).hexdigest()
    return sig

# --------------------
# Static Admin UI
# --------------------
app.mount("/admin", StaticFiles(directory="static/admin", html=True), name="admin")

# --------------------
# API
# --------------------
@app.post("/verify")
def verify(data: dict, db: Session = Depends(db)):
    key = data.get("license_key")
    device = data.get("device_id")

    lic = db.query(License).filter_by(license_key=key, active=True).first()
    if not lic:
        raise HTTPException(403, "Invalid license")

    if lic.expires_at and datetime.utcnow().timestamp() > lic.expires_at:
        raise HTTPException(403, "Expired")

    devices = json.loads(lic.devices)
    if device not in devices:
        if lic.max_devices != -1 and len(devices) >= lic.max_devices:
            raise HTTPException(403, "Device limit reached")
        devices.append(device)
        lic.devices = json.dumps(devices)
        db.commit()

    token = {
        "license": key,
        "device": device,
        "exp": lic.expires_at or int((datetime.utcnow() + timedelta(days=3650)).timestamp())
    }

    return {
        "token": token,
        "signature": sign(token)
    }

# --------------------
# Admin APIs
# --------------------
@app.get("/admin/licenses")
def list_licenses(req: Request, db: Session = Depends(db)):
    admin_auth(req)
    return db.query(License).all()

@app.post("/admin/licenses")
def create_license(data: dict, req: Request, db: Session = Depends(db)):
    admin_auth(req)

    days = int(data.get("expires_in_days", 0))
    expires = None
    if days > 0:
        expires = int((datetime.utcnow() + timedelta(days=days)).timestamp())

    lic = License(
        license_key=data["license_key"],
        max_devices=int(data.get("max_devices", 1)),
        expires_at=expires,
        active=True
    )
    db.add(lic)
    db.commit()
    return {"ok": True}

@app.post("/admin/licenses/{key}/revoke")
def revoke(key: str, req: Request, db: Session = Depends(db)):
    admin_auth(req)
    lic = db.query(License).filter_by(license_key=key).first()
    if not lic:
        raise HTTPException(404)
    lic.active = False
    db.commit()
    return {"ok": True}

@app.delete("/admin/licenses/{key}")
def delete(key: str, req: Request, db: Session = Depends(db)):
    admin_auth(req)
    lic = db.query(License).filter_by(license_key=key).first()
    if not lic:
        raise HTTPException(404)
    db.delete(lic)
    db.commit()
    return {"ok": True}
