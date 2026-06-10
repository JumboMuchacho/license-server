from fastapi import APIRouter, Depends, Request, Header, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from database import get_db
from billing import MpesaTransaction
from security_mpesa import verify_safaricom_ip
from security import verify_raw_signature
from services.mpesa_stk import trigger_stk_push
from services.mpesa_auth import get_mpesa_access_token
from datetime import datetime
# Assuming STKPushRequest is imported from a schemas module
from schemas import STKPushRequest

# 1. Initialize the router
router = APIRouter(prefix="/api/v1/mpesa")

# Background task logic for the callback
def process_callback_data(db: Session, data: dict):
    stk_callback = data.get("Body", {}).get("stkCallback", {})
    checkout_id = stk_callback.get("CheckoutRequestID")
    result_code = stk_callback.get("ResultCode")

    # Double-credit prevention: only update if not already SUCCESS
    transaction = db.query(MpesaTransaction).filter_by(checkout_request_id=checkout_id).first()
    if transaction and transaction.status != "SUCCESS":
        transaction.status = "SUCCESS" if result_code == 0 else "FAILED"
        transaction.completed_at = datetime.utcnow()
        db.commit()

@router.post("/stkpush")
async def initiate_stk_push(
    body: STKPushRequest,
    x_auth_token: str = Header(...),
    db: Session = Depends(get_db)
):
    # 1. Security Check
    if not verify_raw_signature(body.device_id, body.timestamp, x_auth_token):
        raise HTTPException(status_code=403, detail="Invalid request signature.")

    # 2. Get Token
    access_token = get_mpesa_access_token()

    # 3. Call Service
    response = trigger_stk_push(
        db=db,
        phone_number=body.phone_number,
        amount=body.amount,
        license_key=body.device_id, # Assuming device_id is linked to the license
        account_reference=body.device_id,
        access_token=access_token
    )

    return response.json()

@router.post("/callback")
async def mpesa_callback(request: Request, bg_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    # 1. Security: Block requests not originating from Safaricom IP ranges
    await verify_safaricom_ip(request)

    # 2. Extract JSON payload
    data = await request.json()

    # 3. Process asynchronously to return 200 OK immediately
    # Safaricom expects a 200 OK response quickly to stop retrying
    bg_tasks.add_task(process_callback_data, db, data)

    return {"ResultCode": 0, "ResultDesc": "Accepted"}
