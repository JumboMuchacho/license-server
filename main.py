import os
import time
from datetime import datetime, timezone
import logging
import hmac
import hashlib
import json
from typing import Optional

from fastapi import FastAPI, HTTPException, Depends
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from sqlalchemy.orm import Session
from dotenv import load_dotenv

from database import SessionLocal, engine, get_db
import models
from admin_routes import router as admin_router

load_dotenv()
LICENSE_SECRET = os.getenv("LICENSE_SECRET")
OFFLINE_TTL_HOURS = int(os.getenv("TOKEN_TTL_HOURS", 24))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="License Server")
app.include_router(admin_router)
app.mount("/admin-ui", StaticFiles(directory="static/admin", html=True), name="admin-ui")

@app.on_event("startup")
def startup():
    models.Base.metadata.create_all(bind=engine)

class VerifyRequest(BaseModel):
    license_key: str
    device_id: str

def sign_payload(payload: dict) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hmac.new(LICENSE_SECRET.encode(), raw, hashlib.sha256).hexdigest()

@app.post("/verify")
def verify(req: VerifyRequest, db: Session = Depends(get_db)):
    # 1. Modern UTC Timestamp
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    lic = db.query(models.License).filter_by(license_key=req.license_key, active=True).first()
    if not lic:
        raise HTTPException(status_code=404, detail="License invalid")

    # 2. Expiry Check
    if lic.expires_at and lic.expires_at < now:
        raise HTTPException(status_code=410, detail="License expired")

    # 3. Binding Logic
    existing_device = db.query(models.Device).filter_by(device_id=req.device_id).first()
    if existing_device:
        if existing_device.license_id != lic.id:
            raise HTTPException(status_code=403, detail="Device bound to another license")
        existing_device.last_seen = now
        db.commit()
    else:
        if db.query(models.Device).filter_by(license_id=lic.id).count() >= lic.max_devices:
            raise HTTPException(status_code=429, detail="Limit reached")
        db.add(models.Device(license_id=lic.id, device_id=req.device_id, last_seen=now))
        db.commit()

    token = {"license": req.license_key, "device": req.device_id, "exp": int(time.time()) + (OFFLINE_TTL_HOURS * 3600)}
    return {"status": "success", "token": token, "signature": sign_payload(token)}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 10000)))