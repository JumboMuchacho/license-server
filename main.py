import os
import time
import calendar
from datetime import datetime, timezone
from typing import Optional

from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse, FileResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session
from dotenv import load_dotenv

# --- SlowAPI Imports ---
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from database import engine, get_db
import models
from admin_routes import router as admin_router
from security import sign_payload, verify_signature

load_dotenv()

# Initialize the Limiter using the client's remote IP address
limiter = Limiter(key_func=get_remote_address)

app = FastAPI(title="License Server")

# Set up SlowAPI state and custom exception handler
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


# -------------------------------------------------
# Security Headers Middleware
# -------------------------------------------------
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Content-Security-Policy"] = "default-src 'self' 'unsafe-inline' https://unpkg.com; connect-src 'self' https://*.supabase.co;"
    return response


app.include_router(admin_router)


# -------------------------------------------------
# Pydantic Schemas
# -------------------------------------------------

class VerifyRequest(BaseModel):
    license_key: str
    device_id: str
    version: Optional[str] = None


class RulesRequest(BaseModel):
    license_key: str
    device_id: str
    envelope: dict  # Receives the cryptographically structured packet from the client extension


# -------------------------------------------------
# Routes
# -------------------------------------------------

@app.get("/")
def root():
    return RedirectResponse("/admin-ui")


@app.get("/admin-ui")
def admin_ui():
    return FileResponse("static/admin/index.html")


@app.get("/health")
def health():
    return {"status": "ok"}


# Replace your current /api/v1/rules endpoint with this in main.py

@app.post("/api/v1/rules")
def get_secure_rules(payload: dict):
    # TEMPORARY BYPASS: Directly return the rules to test the extension connection
    return {
        "isActive": True,
        "rules": [
            "//div[contains(@class,'commonModal-wrap')]//div[contains(@class,'message') and contains(.,'no USDT transaction')]",
            "//div[contains(@class,'commonModal-wrap')]//div[contains(@class,'buttonBox')]//div[contains(.,'Try Again Later')]"
        ]
    }


# -------------------------------------------------
# Static Files & Lifecycle
# -------------------------------------------------

app.mount("/static", StaticFiles(directory="static"), name="static")


@app.on_event("startup")
def startup():
    models.Base.metadata.create_all(bind=engine)
