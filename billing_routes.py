from fastapi import APIRouter, Depends, Request, Header, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from database import get_db, SessionLocal  # Import SessionLocal for background tasks
from billing import MpesaTransaction
from security_mpesa import verify_safaricom_ips as verify_safaricom_ip
from security import verify_raw_signature
from services.mpesa_stk import trigger_stk_push
from services.mpesa_auth import get_mpesa_access_token
from datetime import datetime
from schemas import STKPushRequest

router = APIRouter(prefix="/api/v1/mpesa")

# Fix: Create a new session inside the task, or the original session will be closed!
def process_callback_data(data: dict):
    db = SessionLocal() # Open new session for background task
    try:
        stk_callback = data.get("Body", {}).get("stkCallback", {})
        checkout_id = stk_callback.get("CheckoutRequestID")
        result_code = stk_callback.get("ResultCode")
        result_desc = stk_callback.get("ResultDesc")

        print(f"DEBUG: Processing callback for {checkout_id}")

        transaction = db.query(MpesaTransaction).filter_by(checkout_request_id=checkout_id).first()

        if transaction:
            transaction.status = "SUCCESS" if result_code == 0 else "FAILED"
            transaction.result_code = result_code
            transaction.result_desc = result_desc
            transaction.completed_at = datetime.utcnow()
            db.commit()
            print(f"DEBUG: Transaction {checkout_id} updated.")
        else:
            print(f"DEBUG: Transaction {checkout_id} not found.")
    finally:
        db.close() # Always close the session

@router.post("/stkpush")
async def initiate_stk_push(
    body: STKPushRequest,
    x_auth_token: str = Header(...),
    db: Session = Depends(get_db)
):
    if not verify_raw_signature(body.device_id, body.timestamp, x_auth_token):
        raise HTTPException(status_code=403, detail="Invalid request signature.")

    new_txn = MpesaTransaction(
        license_key=body.device_id,
        phone_number=str(body.phone_number),
        amount=body.amount,
        status="PENDING"
    )
    db.add(new_txn)
    db.commit()
    db.refresh(new_txn)

    access_token = get_mpesa_access_token()
    response = trigger_stk_push(
        db=db, # Pass db if service needs it, but handle ID update here
        phone_number=body.phone_number,
        amount=body.amount,
        license_key=body.device_id,
        account_reference=body.device_id,
        access_token=access_token
    )

    resp_data = response.json()
    # Explicitly update and commit the ID here
    new_txn.checkout_request_id = resp_data.get("CheckoutRequestID")
    db.commit()

    return resp_data

@router.post("/callback")
async def mpesa_callback(request: Request, bg_tasks: BackgroundTasks):
    await verify_safaricom_ip(request)
    data = await request.json()

    # Do not pass 'db' dependency here, it gets closed after this return!
    bg_tasks.add_task(process_callback_data, data)

    return {"ResultCode": 0, "ResultDesc": "Accepted"}
