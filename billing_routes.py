from fastapi import APIRouter, Depends, Request, Header, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from database import get_db, SessionLocal
from billing import MpesaTransaction
import models
from security_mpesa import verify_safaricom_ips as verify_safaricom_ip
from security import verify_raw_signature
from services.mpesa_stk import trigger_stk_push
from services.mpesa_auth import get_mpesa_access_token
from schemas import STKPushRequest

router = APIRouter(prefix="/api/v1/mpesa")

def process_callback_data(data: dict):
    """Background task to update device token balance directly."""
    db = SessionLocal()
    try:
        stk_callback = data.get("Body", {}).get("stkCallback", {})
        checkout_id = stk_callback.get("CheckoutRequestID")
        result_code = stk_callback.get("ResultCode")

        # 1. Fetch transaction
        txn = db.query(MpesaTransaction).filter_by(checkout_request_id=checkout_id).first()
        if not txn:
            return

        # 2. Extract amount from CallbackMetadata
        metadata = stk_callback.get("CallbackMetadata", {}).get("Item", [])
        amount = next((float(i["Value"]) for i in metadata if i["Name"] == "Amount"), 0)

        # 3. Update Device Balance (amount / 10 = tokens)
        device = db.query(models.Device).filter(models.Device.device_id == txn.device_id).first()

        if device and result_code == 0:
            device.token_balance += int(amount / 10)
            txn.status = "SUCCESS"
            db.commit()
        elif result_code != 0:
            txn.status = "FAILED"
            db.commit()

    except Exception as e:
        print(f"Error in callback processing: {e}")
    finally:
        db.close()

import hmac, hashlib
from security import derive_device_secret

@router.post("/stkpush")
async def initiate_stk_push(
    body: STKPushRequest,
    request: Request,
    db: Session = Depends(get_db)
):
    # 1. Extract Header
    x_auth_token = request.headers.get("x-auth-token") or request.headers.get("X-Auth-Token")

    # 2. Re-calculate exactly what the server expects
    derived_key = derive_device_secret(body.device_id)
    raw_message_string = f"{body.device_id}:{body.timestamp}"
    computed_signature = hmac.new(derived_key, raw_message_string.encode("utf-8"), hashlib.sha256).hexdigest()

    # 3. AUDIT LOGS - This reveals the truth
    print(f"\n--- SIGNATURE AUDIT ---")
    print(f"DEBUG: Device ID: {body.device_id}")
    print(f"DEBUG: Timestamp: {body.timestamp}")
    print(f"DEBUG: Raw String Expected: {raw_message_string}")
    print(f"DEBUG: Server Computed Hash: {computed_signature}")
    print(f"DEBUG: Client Sent Hash:      {x_auth_token}")
    print(f"DEBUG: Match? {computed_signature == x_auth_token}")
    print(f"-----------------------\n")

    if not x_auth_token or computed_signature != x_auth_token:
        raise HTTPException(status_code=403, detail="Invalid request signature.")

    # ... proceed with STK push ...

@router.post("/callback")
async def mpesa_callback(request: Request, bg_tasks: BackgroundTasks):
    try:
        # IP Security check is vital for M-Pesa callbacks
        await verify_safaricom_ip(request)
        data = await request.json()

        # Offload to background to respond to Safaricom immediately
        bg_tasks.add_task(process_callback_data, data)
        return {"ResultCode": 0, "ResultDesc": "Accepted"}
    except Exception as e:
        print(f"Callback security error: {e}")
        raise HTTPException(status_code=400, detail="Invalid request")
