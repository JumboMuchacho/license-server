import os
import requests
import base64
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

# Cache the access token to avoid requesting one for every payment
_token_cache = {
    "token": None,
    "expires_at": datetime.min
}


def get_mpesa_access_token():
    """
    Retrieves and caches an M-Pesa OAuth access token.
    """

    # Return cached token if still valid
    if (
        _token_cache["token"] is not None
        and datetime.now() < _token_cache["expires_at"]
    ):
        return _token_cache["token"]

    # Read environment variables
    consumer_key = os.getenv("MPESA_CONSUMER_KEY", "").strip()
    consumer_secret = os.getenv("MPESA_CONSUMER_SECRET", "").strip()
    env_mode = os.getenv("MPESA_ENV", "sandbox").strip().lower()

    if not consumer_key or not consumer_secret:
        logger.error("M-Pesa consumer credentials are missing.")
        raise Exception("MPESA_CONSUMER_KEY or MPESA_CONSUMER_SECRET is missing.")

    # Select API host
    if env_mode == "production":
        base_url = "https://api.safaricom.co.ke"
    else:
        base_url = "https://sandbox.safaricom.co.ke"

    api_url = f"{base_url}/oauth/v1/generate?grant_type=client_credentials"

    logger.info(f"Requesting OAuth token from: {api_url}")

    # Create Basic Authorization header
    credentials = f"{consumer_key}:{consumer_secret}"
    encoded_credentials = base64.b64encode(
        credentials.encode("utf-8")
    ).decode("utf-8")

    headers = {
        "Authorization": f"Basic {encoded_credentials}",
        "Content-Type": "application/json"
    }

    try:
        response = requests.get(
            api_url,
            headers=headers,
            timeout=15
        )

        logger.info(f"OAuth Status: {response.status_code}")

        if response.status_code != 200:
            logger.error(f"OAuth Response: {response.text}")
            raise Exception(
                f"Failed to obtain access token: {response.text}"
            )

        data = response.json()

        token = data.get("access_token")
        expires_in = int(data.get("expires_in", 3599))

        if not token:
            raise Exception("Safaricom did not return an access token.")

        # Cache token with a 60-second safety buffer
        _token_cache["token"] = token
        _token_cache["expires_at"] = (
            datetime.now() + timedelta(seconds=expires_in - 60)
        )

        logger.info("Successfully obtained M-Pesa access token.")

        return token

    except requests.RequestException as e:
        logger.exception("Network error while requesting OAuth token.")
        raise Exception(f"Network error contacting Safaricom: {e}")

    except ValueError:
        logger.exception("Safaricom returned invalid JSON.")
        raise Exception("Safaricom returned an invalid JSON response.")

    except Exception as e:
        logger.exception("Unexpected OAuth error.")
        raise
