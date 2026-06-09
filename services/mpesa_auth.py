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

    # 2. Fetch new token
    consumer_key = os.getenv("MPESA_CONSUMER_KEY")
    consumer_secret = os.getenv("MPESA_CONSUMER_SECRET")
    api_url = "https://sandbox.safaricom.co.ke/oauth/v1/generate?grant_type=client_credentials"

    response = requests.get(api_url, auth=HTTPBasicAuth(consumer_key, consumer_secret))

    if response.status_code == 200:
        data = response.json()
        token = data["access_token"]
        # Safaricom tokens usually expire in 3600 seconds
        expires_in = int(data["expires_in"])

        # Cache the token and set expiration time
        _token_cache["token"] = token
        _token_cache["expires_at"] = datetime.now() + timedelta(seconds=expires_in - 60)

        return token
    else:
        raise Exception(f"Failed to authenticate with M-Pesa: {response.text}")
