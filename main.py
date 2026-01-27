import os
import time
import datetime
import logging
from typing import Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from dotenv import load_dotenv

from database import SessionLocal, engine
import models
from security import sign_payload

# ----------------------------
# Load environment variables
# ----------------------------
load_dotenv()
LICENSE_SECRET = os.getenv("LICENSE_SECRET")
if not LICENSE_SECRET:
    raise ValueError(
        "LICENSE_SECRET not set! Add it to .env or your environment variables."
    )

logging.basicConfig(level=logging.INFO)

OFFLINE_TTL_HOURS = 48

# ----------------------------
# FastAPI app
# ----------------------------
app = FastAPI(title="License Server")

# ----------------------------
# Startup: initialize DB
# ----------------------------
@app.on_event("startup")
def startup():
    try:
        models.Base.metadata.create_all(bind=engine)
        logging.info("Database ready")
    except Exception as e:
        logging.error(f"DB unavailable: {e}")

# ----------------------------
# Health check endpoint
# ----------------------------
@app.get("/health")
def health():
    return {"status": "ok"}

# ----------------------------
# Root endpoint
# ----------------------------
@app.get("/")
def index():
    return {
        "message": "License Server is running. Use /verify to validate licenses."
    }

# ----------------------------
# License verification endpoint
# ----------------------------
class VerifyRequest(BaseModel):
    license_key: str
    device_id: str
    client_version: Optional[str] = None  # ✅ OPTIONAL now

@app.post("/verify")
def verify(req: VerifyRequest):
    db: Session = SessionLocal()
    try:
        logging.info(
            f"Verify request: license={req.license_key}, "
            f"device={req.device_id}, version={req.client_version}"
        )

        lic = (
            db.query(models.License)
            .filter_by(license_key=req.license_key, active=True)
            .first()
        )

        if not lic:
            raise HTTPException(status_code=404, detail="License invalid")

        if lic.expires_at and lic.expires_at < datetime.datetime.utcnow():
            raise HTTPException(status_code=410, detail="License expired")

        device = (
            db.query(models.Device)
            .filter_by(license_id=lic.id, device_id=req.device_id)
            .first()
        )

        if not device:
            count = (
                db.query(models.Device)
                .filter_by(license_id=lic.id)
                .count()
            )

            if count >= lic.max_devices:
                raise HTTPException(
                    status_code=429, detail="Device limit reached"
                )

            db.add(
                models.Device(
                    license_id=lic.id,
                    device_id=req.device_id
                )
            )
            db.commit()

        # Offline token expiry
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
# Run with Uvicorn
# ----------------------------
if __name__ == "__main__":
    import uvicorn

    PORT = int(os.environ.get("PORT", 10000))
    uvicorn.run(app, host="0.0.0.0", port=PORT)
