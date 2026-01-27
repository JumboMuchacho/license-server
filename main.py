import os
import time
import datetime
import logging
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
LICENSE_SECRET = os.getenv('LICENSE_SECRET')
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
# Health check endpoint (Render requirement)
# ----------------------------
@app.get("/health")
def health():
    return {"status": "ok"}

# ----------------------------
# Optional friendly root endpoint
# ----------------------------
@app.get("/")
def index():
    return {"message": "License Server is running. Use /verify to validate licenses."}

# ----------------------------
# License verification endpoint
# ----------------------------
class VerifyRequest(BaseModel):
    license_key: str
    device_id: str
    client_version: str  # Added to match client and fix 422 error

@app.post("/verify")
def verify(req: VerifyRequest):
    db: Session = SessionLocal()
    try:
        print(f"DEBUG: Received request - license_key={req.license_key}, device_id={req.device_id}, client_version={req.client_version}")  # Debug log
        lic = db.query(models.License).filter_by(
            license_key=req.license_key,
            active=True
        ).first()

        if not lic:
            print("DEBUG: License not found in DB")  # Debug log
            raise HTTPException(404, "License invalid")

        if lic.expires_at and lic.expires_at < datetime.datetime.utcnow():
            print("DEBUG: License expired")  # Debug log
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
                print("DEBUG: Device limit reached")  # Debug log
                raise HTTPException(429, "Device limit reached")

            db.add(models.Device(
                license_id=lic.id,
                device_id=req.device_id
            ))
            db.commit()

        # Token expires in OFFLINE_TTL_HOURS hours
        expires = int(time.time()) + OFFLINE_TTL_HOURS * 3600

        token = {
            "license": req.license_key,
            "device": req.device_id,
            "exp": expires,
        }

        return {
            "token": token,
            "signature": sign_payload(token, LICENSE_SECRET),
        }

    finally:
        db.close()

# ----------------------------
# Run the app using Uvicorn
# ----------------------------
if __name__ == "__main__":
    import uvicorn
    PORT = int(os.environ.get("PORT", 10000))
    uvicorn.run(app, host="0.0.0.0", port=PORT)