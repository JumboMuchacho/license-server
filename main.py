import os
import time
import datetime
import logging
from typing import Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from sqlalchemy.orm import Session
from dotenv import load_dotenv
import httpx

from database import SessionLocal, engine
import models
from security import sign_payload
from admin_routes import router as admin_router
from auth import oauth_router

# ----------------------------
# Load environment variables
# ----------------------------
load_dotenv()

LICENSE_SECRET = os.getenv("LICENSE_SECRET")
SUPABASE_API_KEY = os.getenv("SUPABASE_API_KEY")
SUPABASE_URL = os.getenv("SUPABASE_URL")  # e.g. https://xyz.supabase.co

if not LICENSE_SECRET:
    raise ValueError("LICENSE_SECRET not set")
if not SUPABASE_API_KEY or not SUPABASE_URL:
    raise ValueError("SUPABASE_API_KEY or SUPABASE_URL not set")

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
# Routers
# ----------------------------
app.include_router(admin_router)   # /admin/*
app.include_router(oauth_router)   # other oauth routes if any

# ----------------------------
# OAuth callback endpoint
# ----------------------------
@app.get("/admin/oauth/callback")
async def oauth_callback(request: Request):
    """
    Supabase redirects here after Google login.
    Exchange code for access token, then redirect to /admin-ui
    """
    code = request.query_params.get("code")
    if not code:
        return {"error": "No code received"}

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{SUPABASE_URL}/auth/v1/token",
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": "https://license-server-lewp.onrender.com/admin/oauth/callback",
            },
            headers={"apikey": SUPABASE_API_KEY},
        )
        token_data = resp.json()
        # Optionally, save token_data in session/cookie here for frontend

    # Redirect user to frontend admin UI
    return RedirectResponse(url="/admin-ui")

# ----------------------------
# Startup: initialize DB
# ----------------------------
@app.on_event("startup")
def startup():
    try:
        models.Base.metadata.create_all(bind=engine)
        logging.info("Database ready")
    except Exception as e:
        logging.error(f"DB error: {e}")

# ----------------------------
# Health
# ----------------------------
@app.get("/health")
def health():
    return {"status": "ok"}

# ----------------------------
# Root
# ----------------------------
@app.get("/")
def index():
    return {"message": "License Server running"}

# ----------------------------
# License verification
# ----------------------------
class VerifyRequest(BaseModel):
    license_key: str
    device_id: str
    client_version: Optional[str] = None

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

            db.add(models.Device(license_id=lic.id, device_id=req.device_id))
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
        host=os.getenv("HOST", "0.0.0.0"),
        port=int(os.getenv("PORT", 10000)),
    )
