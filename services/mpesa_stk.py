import os
import httpx
import base64
from datetime import datetime

def trigger_stk_push(db, phone_number: str, amount: int, account_reference: str, access_token: str):
    """
    Builds payload and triggers STK Push to Safaricom.
    Matches the arguments: (db, phone_number, amount, account_reference, access_token)
    """
    url = "https://sandbox.safaricom.co.ke/mpesa/stkpush/v1/processrequest"

    shortcode = os.getenv("MPESA_SHORTCODE")
    passkey = os.getenv("MPESA_PASSKEY")
    callback_url = os.getenv("MPESA_CALLBACK_URL")

    # 1. Prepare Timestamp and Password
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    password = base64.b64encode(f"{shortcode}{passkey}{timestamp}".encode()).decode()

    # 2. Build Payload
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
        "TransactionDesc": "Taptap Topup"
    }

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }

    # 3. Trigger Request
    # Using httpx to match your FastAPI environment
    with httpx.Client() as client:
        response = client.post(url, json=payload, headers=headers)

    return response
