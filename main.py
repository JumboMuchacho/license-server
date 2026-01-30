import os
import time
import datetime
import logging
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from sqlalchemy.orm import Session
from dotenv import load_dotenv
import hmac
import hashlib
import json

from database import SessionLocal, engine
import models

# ----------------------------
# Load environment variables
# ----------------------------
load_dotenv()

LICENSE_SECRET = os.getenv("LICENSE_SECRET")
if not LICENSE_SECRET:
    raise ValueError("LICENSE_SECRET not set")

OFFLINE_TTL_HOURS = int(os.getenv("TOKEN_TTL_HOURS", 24))

logging.basicConfig(level=logging.INFO)

# ----------------------------
# FastAPI app
# ----------------------------
app = FastAPI(title="License Server")

# ----------------------------
# Static Admin UI
# ----------------------------
app.mount(
    "/admin-ui",
    StaticFiles(directory="static/admin", html=True),
    name="admin-ui",
)

# ----------------------------
# Startup
# ----------------------------
@app.on_event("startup")
def startup():
    models.Base.metadata.create_all(bind=engine)
    logging.info("Database ready")

# ----------------------------
# Health
# ----------------------------
@app.get("/")
def index():
    return {"message": "License Server running"}

@app.get("/health")
def health():
    return {"status": "ok"}

# ----------------------------
# Models
# ----------------------------
class VerifyRequest(BaseModel):
    license_key: str
    device_id: str
    client_version: Optional[str] = None

# ----------------------------
# Signing
# ----------------------------
def sign_payload(payload: dict) -> str:
    raw = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False
    ).encode("utf-8")

    return hmac.new(
        LICENSE_SECRET.encode(),
        raw,
        hashlib.sha256
    ).hexdigest()

# ----------------------------
# VERIFY ENDPOINT (CRITICAL)
# ----------------------------
@app.post("/verify")
def verify(req: VerifyRequest):
    db: Session = SessionLocal()
    try:
        lic = (
            db.query(models.License)
            .filter_by(license_key=req.license_key, active=True)
            .first()
        )

        if not lic:
            raise HTTPException(404, "License invalid")

        if lic.expires_at and lic.expires_at < datetime.datetime.utcnow():
            raise HTTPException(410, "License expired")

        device = (
            db.query(models.Device)
            .filter_by(license_id=lic.id, device_id=req.device_id)
            .first()
        )

        if not device:
            count = db.query(models.Device).filter_by(license_id=lic.id).count()
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
        }

        return {
            "token": token,
            "signature": sign_payload(token),
        }

    finally:
        db.close()

# ----------------------------
# Local run
# ----------------------------
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=int(os.getenv("PORT", 10000)),
    )
