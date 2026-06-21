import base64
import os
from datetime import datetime

import httpx


def _mpesa_base_url() -> str:
    return os.getenv("MPESA_BASE_URL", "https://sandbox.safaricom.co.ke").rstrip("/")


def trigger_stk_push(
    db, phone_number: str, amount: int, account_reference: str, access_token: str
):
    url = f"{_mpesa_base_url()}/mpesa/stkpush/v1/processrequest"

    shortcode = os.getenv("MPESA_SHORTCODE")
    passkey = os.getenv("MPESA_PASSKEY")
    callback_url = os.getenv("MPESA_CALLBACK_URL")

    if not shortcode or not passkey or not callback_url:
        raise ValueError("M-Pesa STK configuration is incomplete.")

    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    password = base64.b64encode(f"{shortcode}{passkey}{timestamp}".encode()).decode()

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
        "TransactionDesc": "Taptap Token Topup",
    }

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }

    with httpx.Client(timeout=30.0) as client:
        return client.post(url, json=payload, headers=headers)
