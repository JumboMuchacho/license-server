import os
import requests
import base64
from datetime import datetime, timedelta

_token_cache = {
    "token": None,
    "expires_at": datetime.min
}

def get_mpesa_access_token():
    if _token_cache["token"] and datetime.now() < _token_cache["expires_at"]:
        return _token_cache["token"]

    consumer_key = os.getenv("MPESA_CONSUMER_KEY")
    consumer_secret = os.getenv("MPESA_CONSUMER_SECRET")
    # FIXED: Automatically toggle gateway endpoint domain based on environment selection
    env_mode = os.getenv("MPESA_ENV", "sandbox").lower()
    base_url = "api.safaricom.co.ke" if env_mode == "production" else "sandbox.safaricom.co.ke"

    if not consumer_key or not consumer_secret:
        raise Exception("M-Pesa credentials not configured.")

    credentials = f"{consumer_key}:{consumer_secret}"
    encoded_credentials = base64.b64encode(credentials.encode()).decode()

    api_url = f"https://{base_url}/oauth/v1/generate?grant_type=client_credentials"
    headers = {
        "Authorization": f"Basic {encoded_credentials}"
    }

    try:
        response = requests.get(api_url, headers=headers, timeout=10)

        if response.status_code != 200:
            print(f"DEBUG: Auth Status: {response.status_code}, Body: {response.text}")
            raise Exception(f"Failed to authenticate: {response.text}")

        data = response.json()
        token = data["access_token"]
        expires_in = int(data["expires_in"])

        _token_cache["token"] = token
        _token_cache["expires_at"] = datetime.now() + timedelta(seconds=expires_in - 60)

        return token
    except Exception as e:
        print(f"Exception encountered during safaricom authentication token extraction: {e}")
        raise e
