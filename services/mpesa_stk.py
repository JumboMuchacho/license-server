import base64
import os
import time
import requests
from datetime import datetime

def generate_mpesa_password(shortcode: str, passkey: str) -> str:
    """Generates the base64 encoded password for Daraja."""
    timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
    data_to_encode = f"{shortcode}{passkey}{timestamp}"
    return base64.b64encode(data_to_encode.encode()).decode(), timestamp

def trigger_stk_push(phone_number: int, amount: int, account_reference: str, access_token: str):
    """Builds the payload and triggers the STK Push request."""
    shortcode = os.getenv("MPESA_SHORTCODE")
    passkey = os.getenv("MPESA_PASSKEY")
    callback_url = "https://license-server-lewp.onrender.com/api/v1/mpesa/callback"

    password, timestamp = generate_mpesa_password(shortcode, passkey)

    payload = {
        "BusinessShortCode": shortcode,
        "Password": password,
        "Timestamp": timestamp,
        "TransactionType": "CustomerPayBillOnline",
        "Amount": amount,
        "PartyA": phone_number,
        "PartyB": shortcode,
        "PhoneNumber": phone_number,
        "CallBackURL": callback_url,
        "AccountReference": account_reference,
        "TransactionDesc": "Token Top-up"
    }

    headers = {"Authorization": f"Bearer {access_token}"}

    return requests.post(
        "https://sandbox.safaricom.co.ke/mpesa/stkpush/v1/processrequest",
        json=payload,
        headers=headers
    )
