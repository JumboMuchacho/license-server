import os
import httpx
import base64
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


async def trigger_stk_push(
    db,
    phone_number: str,
    amount: int,
    account_reference: str,
    access_token: str,
):
    """
    Builds and sends an STK Push request to Safaricom.
    """

    # Build the endpoint safely
    base_url = os.getenv("MPESA_BASE_URL", "").rstrip("/")
    url = f"{base_url}/mpesa/stkpush/v1/processrequest"

    shortcode = os.getenv("MPESA_SHORTCODE")
    passkey = os.getenv("MPESA_PASSKEY")
    callback_url = os.getenv("MPESA_CALLBACK_URL")

    if not all([shortcode, passkey, callback_url]):
        raise Exception("Missing one or more M-Pesa environment variables.")

    # Timestamp and password
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")

    password = base64.b64encode(
        f"{shortcode}{passkey}{timestamp}".encode("utf-8")
    ).decode("utf-8")

    payload = {
        "BusinessShortCode": shortcode,
        "Password": password,
        "Timestamp": timestamp,
        "TransactionType": "CustomerPayBillOnline",
        "Amount": int(amount),
        "PartyA": str(phone_number),
        "PartyB": shortcode,
        "PhoneNumber": str(phone_number),
        "CallBackURL": callback_url,
        "AccountReference": account_reference,
        "TransactionDesc": "Taptap Topup",
    }

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }

    logger.info(f"Posting STK Push to: {url}")
    logger.info(f"Phone: {phone_number}")
    logger.info(f"Amount: {amount}")
    logger.info(f"Account Reference: {account_reference}")

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            url,
            json=payload,
            headers=headers,
        )

    logger.info(f"Safaricom Status: {response.status_code}")
    logger.info(f"Safaricom Response: {response.text}")

    # Raise an exception for HTTP errors (4xx/5xx)
    response.raise_for_status()

    return response
