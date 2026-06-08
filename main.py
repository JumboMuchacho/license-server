import hmac
import hashlib
import secrets
from datetime import datetime, timezone
from fastapi import Depends, FastAPI, HTTPException, Request, Header
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy.orm import Session
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from database import engine, get_db
import models

# Initialize Rate Limiter
limiter = Limiter(key_func=get_remote_address)
app = FastAPI(title="License Server")
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Security Headers
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    return response

# Schemas
class VerifyRequest(BaseModel):
    license_key: str
    device_id: str

def verify_token(device_id: str, timestamp: str, token: str, db: Session):
    device = db.query(models.Device).filter(models.Device.device_id == device_id).first()
    if not device or not device.shared_secret:
        return False
    # HMAC verification
    expected = hmac.new(device.shared_secret.encode(), timestamp.encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, token)

@app.post("/api/v1/register")
@limiter.limit("5/minute") # Rate limit registration
def register_device(request: Request, body: VerifyRequest, db: Session = Depends(get_db)):
    lic = db.query(models.License).filter(models.License.license_key == body.license_key, models.License.active == True).first()
    if not lic:
        raise HTTPException(status_code=403, detail="Invalid license")
    device = db.query(models.Device).filter(models.Device.device_id == body.device_id).first()
    if not device:
        new_secret = secrets.token_hex(16)
        device = models.Device(license_id=lic.id, device_id=body.device_id, shared_secret=new_secret)
        db.add(device)
        db.commit()
    return {"status": "success", "shared_secret": device.shared_secret}

@app.post("/api/v1/rules")
@limiter.limit("60/minute")
def get_secure_rules(request: Request, body: dict, x_auth_token: str = Header(...), db: Session = Depends(get_db)):
    device_id = body.get("device_id")
    timestamp = body.get("timestamp")
    if not device_id or not timestamp or not x_auth_token:
        raise HTTPException(status_code=400, detail="Missing parameters")
    if not verify_token(device_id, str(timestamp), x_auth_token, db):
        raise HTTPException(status_code=403, detail="Invalid token")

    device = db.query(models.Device).filter(models.Device.device_id == device_id).first()
    device.last_seen = datetime.now(timezone.utc)
    db.commit()
    return {
        "isActive": True,
        "rules": [
            "//div[contains(@class,'commonModal-wrap')]//div[contains(@class,'message') and contains(.,'no USDT transaction')]",
            "//div[contains(@class,'commonModal-wrap')]//div[contains(@class,'buttonBox')]//div[contains(.,'Try Again Later')]"
        ]
    }

@app.on_event("startup")
def startup():
    models.Base.metadata.create_all(bind=engine)
