import os
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
    transaction_desc = os.getenv(
        "MPESA_TRANSACTION_DESC",
        "Taptap Topup",
    ).strip()

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
    # Production Logging
    # ------------------------------------------------------------------
    logger.info(
        "STK Push | Phone=%s | Amount=%s | Account=%s",
        phone_number,
        amount,
        account_reference,
    )

    # ------------------------------------------------------------------
    # Send request
    # ------------------------------------------------------------------
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            url,
            json=payload,
            headers=headers,
        )

    response.raise_for_status()

    response_json = response.json()

    # ------------------------------------------------------------------
    # Log Result
    # ------------------------------------------------------------------
    if response_json.get("ResponseCode") == "0":
        logger.info(
            "STK Accepted | Checkout=%s | Merchant=%s",
            response_json.get("CheckoutRequestID"),
            response_json.get("MerchantRequestID"),
        )
    else:
        logger.warning(
            "STK Rejected | Code=%s | Desc=%s",
            response_json.get("ResponseCode"),
            response_json.get("ResponseDescription"),
        )

    return response
