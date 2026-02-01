import os
import time
import logging
import hmac
import hashlib
import json
from datetime import datetime, timezone
from typing import Optional, List

from fastapi import FastAPI, HTTPException, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse, FileResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session
from dotenv import load_dotenv

# Import local modules
from database import SessionLocal, engine, get_db
import models
from admin_routes import router as admin_router

# ----------------------------
# Setup & Config
# ----------------------------
load_dotenv()

LICENSE_SECRET = os.getenv("LICENSE_SECRET") 
if not LICENSE_SECRET:
    raise ValueError("LICENSE_SECRET environment variable is not set!")
OFFLINE_TTL_HOURS = int(os.getenv("TOKEN_TTL_HOURS", 3))

logging.basicConfig(
    level=logging.WARNING,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)
logging.getLogger("uvicorn.access").setLevel(logging.WARNING)

app = FastAPI(title="License Server")

# ----------------------------
# 1. Routers & UI Redirects (Updates for Admin Panel)
# ----------------------------

# Include the Admin CRUD routes
app.include_router(admin_router)

# Handle the Supabase Redirect URL specifically
@app.get("/admin-ui")
async def admin_ui():
    """Serves the main Admin HTML file."""
    return FileResponse("static/admin/index.html")

# Redirect root to /admin-ui instead of JSON message
@app.get("/")
async def root():
    return RedirectResponse(url="/admin-ui")

@app.get("/health")
def health():
    return {"status": "ok"}

# Mount the entire static directory so CSS/JS files are accessible
app.mount("/static", StaticFiles(directory="static"), name="static")

# ----------------------------
# Database Initialization
# ----------------------------
@app.on_event("startup")
def startup():
    models.Base.metadata.create_all(bind=engine)
    logger.warning("Database initialized and verified.")

# ----------------------------
# Schemas & Helper
# ----------------------------
class VerifyRequest(BaseModel):
    license_key: str
    device_id: str
    client_version: Optional[str] = None

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
# 3. Verify Route (Keeping your original logic)
# ----------------------------
@app.post("/verify")
def verify(req: VerifyRequest, db: Session = Depends(get_db)):
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    # 1. Look for the target license
    lic = (
        db.query(models.License)
        .filter(models.License.license_key == req.license_key, models.License.active == True)
        .first()
    )

    if not lic:
        raise HTTPException(status_code=404, detail="License invalid or revoked")

    # 2. Check if target license is expired
    if lic.expires_at and lic.expires_at < now:
        raise HTTPException(status_code=410, detail="License expired")

    # 3. Handle Device Binding & Migration Logic
    existing_device = db.query(models.Device).filter_by(device_id=req.device_id).first()

    if existing_device:
        if existing_device.license_id == lic.id:
            existing_device.last_seen = now
            db.commit()
        else:
            old_lic = db.query(models.License).filter_by(id=existing_device.license_id).first()
            is_old_dead = not old_lic or not old_lic.active or (old_lic.expires_at and old_lic.expires_at < now)
            
            if is_old_dead:
                count = db.query(models.Device).filter_by(license_id=lic.id).count()
                if count >= lic.max_devices:
                    raise HTTPException(status_code=429, detail="Target license is full")

                existing_device.license_id = lic.id
                existing_device.last_seen = now
                db.commit()
                logger.warning(f"Device {req.device_id} migrated to license {lic.license_key}")
            else:
                raise HTTPException(status_code=403, detail="Device is still bound to another active license")
    else:
        count = db.query(models.Device).filter_by(license_id=lic.id).count()
        if count >= lic.max_devices:
            raise HTTPException(status_code=429, detail="Maximum device limit reached")

        new_device = models.Device(
            license_id=lic.id,
            device_id=req.device_id,
            last_seen=now
        )
        db.add(new_device)
        db.commit()

    # 4. Generate signed response
    expires = int(time.time()) + (OFFLINE_TTL_HOURS * 3600)
    
    token = {
        "license": req.license_key,
        "device": req.device_id,
        "exp": expires,
    }

    return {
        "status": "success",
        "token": token,
        "signature": sign_payload(token),
    }

if __name__ == "__main__":
    import uvicorn
    # Automatically use 0.0.0.0 for Render, otherwise 127.0.0.1 for local dev
    host = "0.0.0.0" if os.environ.get("RENDER") else "127.0.0.1"   # nosec B104
    port = int(os.environ.get("PORT", 10000))
    
    # # nosec B104 tells Bandit this is intentional
    uvicorn.run(app, host=host, port=port)  