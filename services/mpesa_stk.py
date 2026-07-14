import os
import json
import httpx
import base64
import logging
from datetime import datetime
from zoneinfo import ZoneInfo

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

    # ------------------------------------------------------------------
    # Endpoint
    # ------------------------------------------------------------------
    base_url = os.getenv("MPESA_BASE_URL", "").rstrip("/")
    url = f"{base_url}/mpesa/stkpush/v1/processrequest"

    # ------------------------------------------------------------------
    # Credentials
    # ------------------------------------------------------------------
    business_shortcode = os.getenv("MPESA_SHORTCODE", "").strip()
    party_b = os.getenv("MPESA_PARTY_B", "").strip() or business_shortcode
    passkey = os.getenv("MPESA_PASSKEY", "").strip()
    callback_url = os.getenv("MPESA_CALLBACK_URL", "").strip()
    transaction_desc = os.getenv("MPESA_TRANSACTION_DESC", "Taptap Topup").strip()

    if not all([business_shortcode, party_b, passkey, callback_url]):
        raise Exception(
            "Missing one or more required M-Pesa environment variables."
        )

    # ------------------------------------------------------------------
    # Timestamp
    # ------------------------------------------------------------------
    timestamp = datetime.now(
        ZoneInfo("Africa/Nairobi")
    ).strftime("%Y%m%d%H%M%S")

    # ------------------------------------------------------------------
    # Password
    # Password MUST ALWAYS use BusinessShortCode + Passkey + Timestamp
    # ------------------------------------------------------------------
    password = base64.b64encode(
        f"{business_shortcode}{passkey}{timestamp}".encode("utf-8")
    ).decode("utf-8")

    # ------------------------------------------------------------------
    # Payload
    # ------------------------------------------------------------------
    payload = {
        "BusinessShortCode": business_shortcode,
        "Password": password,
        "Timestamp": timestamp,
        "TransactionType": "CustomerBuyGoodsOnline",
        "Amount": int(amount),
        "PartyA": str(phone_number),
        "PartyB": str(party_b),
        "PhoneNumber": str(phone_number),
        "CallBackURL": callback_url,
        "AccountReference": str(account_reference),
        "TransactionDesc": transaction_desc,
    }

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }

    # ------------------------------------------------------------------
    # DEBUG LOGGING
    # ------------------------------------------------------------------
    logger.info("=" * 60)
    logger.info("STK PUSH REQUEST")
    logger.info("=" * 60)

    logger.info(f"Endpoint: {url}")
    logger.info(f"BusinessShortCode: {repr(business_shortcode)}")
    logger.info(f"PartyB: {repr(party_b)}")
    logger.info(f"Timestamp: {timestamp}")
    logger.info(f"Password: {password}")
    logger.info(f"PhoneNumber: {repr(phone_number)}")
    logger.info(f"Amount: {amount}")
    logger.info(f"Callback URL: {repr(callback_url)}")
    logger.info(f"AccountReference: {repr(account_reference)}")
    logger.info(f"TransactionDesc: {repr(transaction_desc)}")

    logger.info("Payload:")
    logger.info(json.dumps(payload, indent=4))

    logger.info("=" * 60)

    # ------------------------------------------------------------------
    # Send request
    # ------------------------------------------------------------------
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            url,
            json=payload,
            headers=headers,
        )

    # ------------------------------------------------------------------
    # Response logging
    # ------------------------------------------------------------------
    logger.info("=" * 60)
    logger.info("SAFARICOM RESPONSE")
    logger.info("=" * 60)
    logger.info(f"HTTP Status: {response.status_code}")
    logger.info(response.text)
    logger.info("=" * 60)

    response.raise_for_status()

    return response
