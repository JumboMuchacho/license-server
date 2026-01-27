from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
import datetime
import logging
import time
import os
from dotenv import load_dotenv  # <-- added

from database import SessionLocal, engine
import models
from security import sign_payload

# ----------------------------
# Load LICENSE_SECRET from .env or environment
# ----------------------------
load_dotenv()  # loads .env if present

LICENSE_SECRET = os.getenv('LICENSE_SECRET')

if not LICENSE_SECRET:
    raise ValueError(
        "LICENSE_SECRET not set! Add it to .env or your environment variables."
    )

logging.basicConfig(level=logging.INFO)

CLIENT_VERSION = "1.0.0"
OFFLINE_TTL_HOURS = 48

app = FastAPI(title="License Server")


@app.on_event("startup")
def startup():
    try:
        models.Base.metadata.create_all(bind=engine)
        logging.info("DB ready")
    except Exception as e:
        logging.error(f"DB unavailable: {e}")


class VerifyRequest(BaseModel):
    license_key: str
    device_id: str
    client_version: str


@app.post("/verify")
def verify(req: VerifyRequest):
    db: Session = SessionLocal()
    try:
        lic = db.query(models.License).filter_by(
            license_key=req.license_key,
            active=True
        ).first()

        if not lic:
            raise HTTPException(404, "License invalid")

        if req.client_version < lic.min_client_version:
            raise HTTPException(426, "Client update required")

        if lic.expires_at and lic.expires_at < datetime.datetime.utcnow():
            raise HTTPException(410, "License expired")

        device = db.query(models.Device).filter_by(
            license_id=lic.id,
            device_id=req.device_id
        ).first()

        if not device:
            count = db.query(models.Device).filter_by(
                license_id=lic.id
            ).count()
            if count >= lic.max_devices:
                raise HTTPException(429, "Device limit reached")

            db.add(models.Device(
                license_id=lic.id,
                device_id=req.device_id
            ))
            db.commit()

        expires = int(time.time()) + OFFLINE_TTL_HOURS * 3600

        token = {
            "license": req.license_key,
            "device": req.device_id,
            "exp": expires,
            "v": req.client_version,
        }

        # Pass LICENSE_SECRET to sign_payload
        return {
            "token": token,
            "signature": sign_payload(token, LICENSE_SECRET),
        }

    finally:
        db.close()
