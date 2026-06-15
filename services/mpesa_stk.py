import base64
import os
import requests
from datetime import datetime
from sqlalchemy.orm import Session
from billing import MpesaTransaction

def format_phone_number(phone: str) -> int:
    """Normalizes phone input to Safaricom 254XXXXXXXXX format."""
    phone = str(phone).strip()

    # Remove leading '+'
    if phone.startswith("+"):
        phone = phone[1:]

    # If it starts with 0, replace with 254
    if phone.startswith("0"):
        phone = "254" + phone[1:]
    # If it's just the number (no prefix), assume 254 prefix
    elif not phone.startswith("254"):
        phone = "254" + phone

    return int(phone)

def generate_mpesa_password(shortcode: str, passkey: str) -> tuple[str, str]:
    """Generates the base64 encoded password and timestamp for Daraja."""
    timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
    data_to_encode = f"{shortcode}{passkey}{timestamp}"
    password = base64.b64encode(data_to_encode.encode()).decode()
    return password, timestamp

def trigger_stk_push(db: Session, phone_number: str, amount: int, device_id: str, access_token: str):
    """Builds payload and triggers STK Push with normalized phone formatting."""
    shortcode = os.getenv("MPESA_SHORTCODE")
    passkey = os.getenv("MPESA_PASSKEY")
    callback_url = os.getenv("MPESA_CALLBACK_URL")

    if not all([shortcode, passkey, callback_url]):
        raise Exception("M-Pesa STK configuration (Shortcode/Passkey/CallbackURL) missing.")

    # 1. Normalize Phone Number
    formatted_phone = format_phone_number(phone_number)

    # 2. Generate Credentials
    password, timestamp = generate_mpesa_password(shortcode, passkey)

    # 3. Build Payload
    payload = {
        "BusinessShortCode": shortcode,
        "Password": password,
        "Timestamp": timestamp,
        "TransactionType": "CustomerPayBillOnline",
        "Amount": amount,
        "PartyA": formatted_phone,
        "PartyB": shortcode,
        "PhoneNumber": formatted_phone,
        "CallBackURL": callback_url,
        "AccountReference": device_id,
        "TransactionDesc": "Token Top-up"
    }

    headers = {"Authorization": f"Bearer {access_token}"}

    # 4. Trigger Request
    try:
        response = requests.post(
            "https://sandbox.safaricom.co.ke/mpesa/stkpush/v1/processrequest",
            json=payload,
            headers=headers,
            timeout=15
        )
        return response
    except requests.exceptions.RequestException as e:
        print(f"DEBUG: STK Push Request Failed: {e}")
        raise e
