import os
import requests
from fastapi import Security, HTTPException, status
from fastapi.security import HTTPBearer

oauth_scheme = HTTPBearer()

SUPABASE_URL = os.getenv("SUPABASE_URL")
# IMPORTANT: This MUST be the 'service_role' key from Supabase settings
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY")


def verify_oauth(token=Security(oauth_scheme)) -> dict:
    if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
        raise HTTPException(status_code=500, detail="Supabase config missing")

    headers = {
        "apikey": SUPABASE_SERVICE_KEY,
        "Authorization": f"Bearer {token.credentials}",
    }

    try:
        resp = requests.get(
            f"{SUPABASE_URL.rstrip('/')}/auth/v1/user",
            headers=headers,
            timeout=10,
        )
    except Exception as e:
        raise HTTPException(
            status_code=503, detail=f"Auth Service Unreachable: {str(e)}"
        )

    if resp.status_code != 200:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired admin session",
        )

    user = resp.json()
    user_email = user.get("email")

    allowed_admins = [
        email.strip()
        for email in os.getenv("ADMIN_EMAILS", "").split(",")
        if email.strip()
    ]

    if not allowed_admins:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Admin access is not configured.",
        )

    if user_email not in allowed_admins:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Access denied: {user_email} is not an admin.",
        )

    return user
