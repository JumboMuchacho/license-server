import os
import requests
from fastapi import Security, HTTPException, status
from fastapi.security import HTTPBearer

# Initialize bearer scheme
oauth_scheme = HTTPBearer()

# CONFIG: Ensure these are set in your .env or Render dashboard
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY")

def verify_oauth(token=Security(oauth_scheme)) -> dict:
    """
    Verify Supabase JWT access token by calling the Supabase Auth API.
    Only allows users listed in ADMIN_EMAILS.
    """
    if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
        raise HTTPException(
            status_code=500, 
            detail="Server configuration error: Supabase credentials missing"
        )

    # 1. Ask Supabase "Who does this token belong to?"
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
    except requests.exceptions.RequestException:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Could not reach Supabase authentication service"
        )

    # 2. Check if token is valid
    if resp.status_code != 200:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired admin session",
        )

    user = resp.json()
    user_email = user.get("email")

    # 3. Check Admin Permissions
    # In your .env, set ADMIN_EMAILS=yourname@gmail.com,other@gmail.com
    allowed_admins = [
        email.strip()
        for email in os.getenv("ADMIN_EMAILS", "").split(",")
        if email.strip()
    ]

    if allowed_admins and user_email not in allowed_admins:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Access denied: {user_email} is not an authorized admin.",
        )

    return user