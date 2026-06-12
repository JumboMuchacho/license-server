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

        # 1. Fetch transaction using the checkout_id
        txn = db.query(MpesaTransaction).filter_by(checkout_request_id=checkout_id).first()
        if not txn: return

        # 2. Extract amount
        metadata = stk_callback.get("CallbackMetadata", {}).get("Item", [])
        amount = next((float(i["Value"]) for i in metadata if i["Name"] == "Amount"), 0)

        # 3. Direct lookup and update the Device (No License middleman)
        device = db.query(models.Device).filter(models.Device.device_id == txn.device_id).first()

        if device and result_code == 0:
            device.token_balance += int(amount)
            txn.status = "SUCCESS"
            db.commit()

    finally:
        db.close()

@router.post("/stkpush")
async def initiate_stk_push(
    body: STKPushRequest,
    x_auth_token: str = Header(...),
    db: Session = Depends(get_db)
):
    # 1. Signature Verification
    if not verify_raw_signature(body.device_id, body.timestamp, x_auth_token):
        raise HTTPException(status_code=403, detail="Invalid request signature.")

    # 2. Direct Device Lookup
    device = db.query(models.Device).filter(models.Device.device_id == body.device_id).first()
    if not device:
        raise HTTPException(status_code=404, detail="Device not registered.")

    # 3. Trigger M-Pesa STK Push
    access_token = get_mpesa_access_token()
    response = trigger_stk_push(
        db=db,
        phone_number=body.phone_number,
        amount=body.amount,
        account_reference=device.device_id, # Use device_id as ref
        access_token=access_token
    )

    resp_data = response.json()
    checkout_id = resp_data.get("CheckoutRequestID")

    if checkout_id:
        try:
            # 4. Store transaction linked to device_id
            new_txn = MpesaTransaction(
                device_id=device.device_id, # Linked to device, not license
                phone_number=str(body.phone_number),
                amount=body.amount,
                status="PENDING",
                checkout_request_id=checkout_id
            )
            db.add(new_txn)
            db.commit()
        except Exception:
            db.rollback()
            raise HTTPException(status_code=500, detail="Transaction storage failed.")
    else:
        raise HTTPException(status_code=400, detail=f"M-Pesa rejected request: {resp_data}")

    return resp_data

@router.post("/callback")
async def mpesa_callback(request: Request, bg_tasks: BackgroundTasks):
    try:
        await verify_safaricom_ip(request)
        data = await request.json()
        bg_tasks.add_task(process_callback_data, data)
        return {"ResultCode": 0, "ResultDesc": "Accepted"}
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid request")
