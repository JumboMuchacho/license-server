from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
import datetime
import logging

from database import SessionLocal, engine
import models
from admin_routes import router as admin_router

# -------------------------
# Logging
# -------------------------
logging.basicConfig(level=logging.INFO)

# -------------------------
# App initialization
# -------------------------
app = FastAPI(title="License Server")

@app.on_event("startup")
def on_startup():
    logging.info("Starting License Server...")

    # 🚑 Do NOT crash app if DB is temporarily unavailable
    try:
        models.Base.metadata.create_all(bind=engine)
        logging.info("DB ready.")
    except Exception as e:
        logging.error(f"DB unavailable at startup: {e}")

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
# Health checks
# -------------------------
@app.get("/")
def root():
    return {"status": "License server running"}

@app.get("/health")
def health():
    return {"status": "ok"}

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

        # Use UTC for consistency across servers
        now = datetime.datetime.utcnow()
        if lic.expires_at and lic.expires_at < now:
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

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logging.error(f"Verification error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")
    finally:
        db.close()
