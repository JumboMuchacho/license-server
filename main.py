from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
import datetime
import logging

from database import SessionLocal, engine
import models
from admin_routes import router as admin_router

logging.basicConfig(level=logging.INFO)

app = FastAPI(title="License Server")


@app.on_event("startup")
def on_startup():
    logging.info("Starting License Server...")

    # 🚑 DO NOT FAIL APP STARTUP IF DB IS DOWN
    try:
        models.Base.metadata.create_all(bind=engine)
        logging.info("DB tables verified.")
    except Exception as e:
        logging.error(f"DB init skipped: {e}")


app.include_router(admin_router)


class VerifyRequest(BaseModel):
    license_key: str
    device_id: str


@app.get("/")
def root():
    return {"status": "License server running"}


@app.get("/health")
def health():
    return {"status": "ok"}


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

        now = datetime.datetime.utcnow()
        if lic.expires_at and lic.expires_at < now:
            raise HTTPException(status_code=410, detail="License expired")

        existing = db.query(models.Device).filter_by(
            license_id=lic.id,
            device_id=req.device_id
        ).first()

        if existing:
            return {"status": "ok", "message": "Device verified"}

        device_count = db.query(models.Device).filter_by(
            license_id=lic.id
        ).count()

        if device_count >= lic.max_devices:
            raise HTTPException(status_code=429, detail="Device limit reached")

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
        logging.error(e)
        raise HTTPException(status_code=500, detail="Internal server error")
    finally:
        db.close()
