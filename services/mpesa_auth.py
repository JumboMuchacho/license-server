import os
import requests
from datetime import datetime, timedelta
from requests.auth import HTTPBasicAuth

# In-memory cache
_token_cache = {
    "token": None,
    "expires_at": datetime.min
}

def get_mpesa_access_token():
    # 1. Check if token is still valid (with a 60-second buffer)
    if _token_cache["token"] and datetime.now() < _token_cache["expires_at"]:
        return _token_cache["token"]

    # 2. Fetch credentials with fallback/check
    consumer_key = os.getenv("MPESA_CONSUMER_KEY")
    consumer_secret = os.getenv("MPESA_CONSUMER_SECRET")

    if not consumer_key or not consumer_secret:
        print("DEBUG: Missing M-Pesa credentials in environment variables.")
        raise Exception("M-Pesa credentials not configured.")

    api_url = "https://sandbox.safaricom.co.ke/oauth/v1/generate?grant_type=client_credentials"

    try:
        response = requests.get(api_url, auth=HTTPBasicAuth(consumer_key, consumer_secret), timeout=10)

        # Log response status for troubleshooting
        if response.status_code != 200:
            print(f"DEBUG: M-Pesa Auth failed. Status: {response.status_code}, Response: {response.text}")
            raise Exception(f"Failed to authenticate: {response.text}")

        data = response.json()
        token = data["access_token"]
        expires_in = int(data.get("expires_in", 3600))

        # Cache the token
        _token_cache["token"] = token
        _token_cache["expires_at"] = datetime.now() + timedelta(seconds=expires_in - 60)

        return token

    except requests.exceptions.RequestException as e:
        print(f"DEBUG: Network error connecting to M-Pesa: {e}")
        raise Exception("Could not connect to M-Pesa authentication service.")
