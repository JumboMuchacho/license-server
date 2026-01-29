import os
import requests
from fastapi import APIRouter, Security, HTTPException, status
from fastapi.security import HTTPBearer

oauth_scheme = HTTPBearer()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise RuntimeError("Supabase environment variables not set")

oauth_router = APIRouter(prefix="/admin/oauth", tags=["oauth"])


def verify_oauth(token=Security(oauth_scheme)) -> dict:
    """
    Verify Supabase JWT access token.
    """
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {token.credentials}",
    }

    resp = requests.get(
        f"{SUPABASE_URL}/auth/v1/user",
        headers=headers,
        timeout=20,
    )

    if resp.status_code != 200:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )

    user = resp.json()

    # Optional admin allowlist
    allowed_admins = [
        email.strip()
        for email in os.getenv("ADMIN_EMAILS", "").split(",")
        if email.strip()
    ]

    if allowed_admins and user.get("email") not in allowed_admins:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access denied",
        )

    return user


@oauth_router.get("/callback")
def oauth_callback(code: str):
    """
    Supabase OAuth redirect endpoint.

    Supabase exchanges the code internally and redirects
    the browser to the admin UI with an active session.
    """
    return {
        "status": "ok",
        "message": "OAuth login successful. You may close this tab.",
    }
