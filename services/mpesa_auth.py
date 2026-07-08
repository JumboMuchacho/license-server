import os
import requests
import base64
import logging
from datetime import datetime, timedelta

# Setup logging properly
logger = logging.getLogger(__name__)

_token_cache = {
    "token": None,
    "expires_at": datetime.min
}

def get_mpesa_access_token():
    # ... (cache check) ...
    consumer_key = os.getenv("MPESA_CONSUMER_KEY")
    consumer_secret = os.getenv("MPESA_CONSUMER_SECRET")
    env_mode = os.getenv("MPESA_ENV", "sandbox").lower()
    base_url = "api.safaricom.co.ke" if env_mode == "production" else "sandbox.safaricom.co.ke"

    # DEFINE THIS FIRST
    api_url = f"https://{base_url}/oauth/v1/generate?grant_type=client_credentials"

    # THEN PRINT IT
    print(f"DEBUG: Target URL: {api_url}")
    if _token_cache["token"] and datetime.now() < _token_cache["expires_at"]:
        return _token_cache["token"]

    # Tweak: Strip whitespace to prevent corruption from env variable formatting
    consumer_key = os.getenv("MPESA_CONSUMER_KEY", "").strip()
    consumer_secret = os.getenv("MPESA_CONSUMER_SECRET", "").strip()

    env_mode = os.getenv("MPESA_ENV", "sandbox").lower()
    base_url = "api.safaricom.co.ke" if env_mode == "production" else "sandbox.safaricom.co.ke"

    if not consumer_key or not consumer_secret:
        logger.error("M-Pesa credentials missing in environment.")
        raise Exception("M-Pesa credentials not configured.")

    # Tweak: Explicitly encode the combined string
    credentials = f"{consumer_key}:{consumer_secret}"
    encoded_credentials = base64.b64encode(credentials.encode('utf-8')).decode('utf-8')

    api_url = f"https://{base_url}/oauth/v1/generate?grant_type=client_credentials"
    headers = {
        "Authorization": f"Basic {encoded_credentials}",
        "Content-Type": "application/json"
    }

    try:
        response = requests.get(api_url, headers=headers, timeout=15)

        if response.status_code != 200:
            # Tweak: Log the URL being hit so you can confirm if it's hitting sandbox or live
            logger.error(f"Auth failed. URL: {api_url} | Status: {response.status_code} | Body: {response.text}")
            raise Exception(f"Failed to authenticate: {response.text}")

        data = response.json()
        token = data["access_token"]
        # Convert expires_in to int and subtract 60s as a buffer
        expires_in = int(data.get("expires_in", 3599))

        _token_cache["token"] = token
        _token_cache["expires_at"] = datetime.now() + timedelta(seconds=expires_in - 60)

        return token
    except Exception as e:
        logger.error(f"Critical error during Safaricom token extraction: {str(e)}")
        raise e
