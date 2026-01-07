from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
import datetime

from database import SessionLocal, engine, apply_pending_migrations
import models
from admin_routes import router as admin_router

# -------------------------
# App initialization
# -------------------------
app = FastAPI(title="License Server")

# -------------------------
# DB setup (run once)
# -------------------------
models.Base.metadata.create_all(bind=engine)
apply_pending_migrations()

# -------------------------
# Routers
# -------------------------
app.include_router(admin_router)


# -------------------------
# Schemas
# -------------------------
class VerifyRequest(BaseModel):
    license_key: str
    device_id: str


# -------------------------
# Health check (optional but recommended)
# -------------------------
@app.get("/")
def root():
    return {"status": "License server running"}


# -------------------------
# License verification
# -------------------------
@app.post("/verify")
def verify(req: VerifyRequest):
    db: Session = SessionLocal()
    try:
        lic = db.query(models.License).filter_by(
            license_key=req.license_key,
            active=True
        ).first()

        if not lic:
            raise HTTPException(status_code=404, detail="License not found or inactive")

        if lic.expires_at and lic.expires_at < datetime.datetime.utcnow():
            raise HTTPException(status_code=410, detail="License expired")

        # Check if device already registered
        existing = db.query(models.Device).filter_by(
            license_id=lic.id,
            device_id=req.device_id
        ).first()

        if existing:
            return {"status": "ok", "message": "Device verified"}

        # Enforce device limit
        device_count = db.query(models.Device).filter_by(
            license_id=lic.id
        ).count()

        if device_count >= lic.max_devices:
            raise HTTPException(status_code=429, detail="Device limit reached")

        # Register new device
        db.add(models.Device(
            license_id=lic.id,
            device_id=req.device_id
        ))
        db.commit()

        return {"status": "ok", "message": "Device registered and verified"}

    finally:
        db.close()
