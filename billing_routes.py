# billing_routes.py
from fastapi import APIRouter, Depends, HTTPException, Header
from pydantic import BaseModel
from database import get_db
from sqlalchemy.orm import Session
from security import verify_raw_signature
from services.mpesa_auth import get_mpesa_access_token # Assuming you created this
import requests
import os
import time

router = APIRouter(prefix="/api/v1/mpesa", tags=["Billing"])

class STKPushRequest(BaseModel):
    phone_number: str
    amount: int
    device_id: str
    timestamp: int

@router.post("/stkpush")
async def initiate_stk_push(
    body: STKPushRequest,
    x_auth_token: str = Header(...),
    db: Session = Depends(get_db)
):
    # 1. Security: Verify the device signature
    if not verify_raw_signature(body.device_id, body.timestamp, x_auth_token):
        raise HTTPException(status_code=403, detail="Invalid request signature.")

    # 2. Prepare Daraja STK Push payload
    access_token = get_mpesa_access_token()
    headers = {"Authorization": f"Bearer {access_token}"}

    # Generate timestamp and password for M-Pesa
    timestamp = time.strftime("%Y%m%d%H%M%S")
    passkey = os.getenv("MPESA_PASSKEY")
    shortcode = os.getenv("MPESA_SHORTCODE")
    password = f"{shortcode}{passkey}{timestamp}".encode().hex()

    payload = {
        "BusinessShortCode": shortcode,
        "Password": password,
        "Timestamp": timestamp,
        "TransactionType": "CustomerPayBillOnline",
        "Amount": body.amount,
        "PartyA": body.phone_number,
        "PartyB": shortcode,
        "PhoneNumber": body.phone_number,
        "CallBackURL": "https://license-server-lewp.onrender.com/api/v1/mpesa/callback",
        "AccountReference": body.device_id,
        "TransactionDesc": "Token Top-up"
    }

    # 3. Call Daraja API
    response = requests.post(
        "https://sandbox.safaricom.co.ke/mpesa/stkpush/v1/processrequest",
        json=payload,
        headers=headers
    )

    return response.json()
