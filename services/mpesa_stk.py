import base64
import os
import requests
from datetime import datetime
from sqlalchemy.orm import Session
from billing import MpesaTransaction

def generate_mpesa_password(shortcode: str, passkey: str) -> str:
    """Generates the base64 encoded password for Daraja."""
    timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
    data_to_encode = f"{shortcode}{passkey}{timestamp}"
    return base64.b64encode(data_to_encode.encode()).decode(), timestamp

def trigger_stk_push(db: Session, phone_number: int, amount: int, license_key: str, account_reference: str, access_token: str):
    """Builds payload and triggers STK Push."""
    shortcode = os.getenv("MPESA_SHORTCODE")
    passkey = os.getenv("MPESA_PASSKEY")
    callback_url = os.getenv("MPESA_CALLBACK_URL")

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

    # Trigger the request
    response = requests.post(
        "https://sandbox.safaricom.co.ke/mpesa/stkpush/v1/processrequest",
        json=payload,
        headers=headers,
        timeout=10
    )

    # Note: We no longer create the transaction record here because
    # billing_routes.py handles it to avoid duplicate entries.
    return response
