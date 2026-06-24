from fastapi import APIRouter, Depends, Request, Header, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from database import get_db, SessionLocal
from billing import MpesaTransaction
import models
from security_mpesa import verify_safaricom_ips as verify_safaricom_ip
from security import verify_raw_signature, derive_device_secret
from services.mpesa_stk import trigger_stk_push
from services.mpesa_auth import get_mpesa_access_token
from schemas import STKPushRequest
import hmac, hashlib

router = APIRouter(prefix="/api/v1/mpesa")

def process_callback_data(data: dict):
    """Background task to update device token balance directly."""
    db = SessionLocal()
    try:
        stk_callback = data.get("Body", {}).get("stkCallback", {})
        checkout_id = stk_callback.get("CheckoutRequestID")
        result_code = stk_callback.get("ResultCode")

        txn = db.query(MpesaTransaction).filter_by(checkout_request_id=checkout_id).first()
        if not txn: return

        metadata = stk_callback.get("CallbackMetadata", {}).get("Item", [])
        amount = next((float(i["Value"]) for i in metadata if i["Name"] == "Amount"), 0)

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

@router.post("/stkpush")
async def initiate_stk_push(
    body: STKPushRequest,
    request: Request,
    db: Session = Depends(get_db)
):
    # 1. Signature Verification
    x_auth_token = request.headers.get("x-auth-token") or request.headers.get("X-Auth-Token")

    derived_key = derive_device_secret(body.device_id)
    raw_message_string = f"{body.device_id}:{body.timestamp}"
    computed_signature = hmac.new(derived_key, raw_message_string.encode("utf-8"), hashlib.sha256).hexdigest()

    if not x_auth_token or not hmac.compare_digest(computed_signature, x_auth_token):
        raise HTTPException(status_code=403, detail="Invalid request signature.")

    # 2. Validate Device
    device = db.query(models.Device).filter(models.Device.device_id == body.device_id).first()
    if not device:
        raise HTTPException(status_code=404, detail="Device not registered.")

    # 3. Trigger M-Pesa
    access_token = get_mpesa_access_token()
    print(f"DEBUG: Triggering STK for {body.phone_number} with token {access_token[:10]}...")

    response = await trigger_stk_push(
        db=db,
        phone_number=body.phone_number,
        amount=body.amount,
        account_reference=device.device_id,
        access_token=access_token
    )

    resp_data = response.json()
    print(f"DEBUG: SAFARICOM RAW RESPONSE: {resp_data}")

    # 4. Handle Response
    if "CheckoutRequestID" in resp_data:
        new_txn = MpesaTransaction(
            device_id=device.device_id,
            phone_number=str(body.phone_number),
            amount=body.amount,
            status="PENDING",
            checkout_request_id=resp_data.get("CheckoutRequestID")
        )
        db.add(new_txn)
        db.commit()
        return resp_data
    else:
        raise HTTPException(status_code=400, detail=f"Safaricom Error: {resp_data}")

@router.post("/callback")
async def mpesa_callback(request: Request, bg_tasks: BackgroundTasks):
    try:
        await verify_safaricom_ip(request)
        data = await request.json()
        bg_tasks.add_task(process_callback_data, data)
        return {"ResultCode": 0, "ResultDesc": "Accepted"}
    except Exception as e:
        print(f"Callback security error: {e}")
        raise HTTPException(status_code=400, detail="Invalid request")
