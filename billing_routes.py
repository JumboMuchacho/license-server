from fastapi import APIRouter, Depends, Request, Header, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from database import get_db, SessionLocal
from billing import MpesaTransaction
from models import License
from security_mpesa import verify_safaricom_ips as verify_safaricom_ip
from security import verify_raw_signature
from services.mpesa_stk import trigger_stk_push
from services.mpesa_auth import get_mpesa_access_token
from datetime import datetime
from schemas import STKPushRequest

router = APIRouter(prefix="/api/v1/mpesa")

def process_callback_data(data: dict):
    """Background task to handle M-Pesa callback."""
    db = SessionLocal()
    try:
        stk_callback = data.get("Body", {}).get("stkCallback", {})
        checkout_id = stk_callback.get("CheckoutRequestID")
        result_code = stk_callback.get("ResultCode")
        result_desc = stk_callback.get("ResultDesc")

        print(f"DEBUG: Processing callback for {checkout_id}")

        # Search by ID, then fallback to recent PENDING
        transaction = db.query(MpesaTransaction).filter_by(checkout_request_id=checkout_id).first()
        if not transaction:
            transaction = db.query(MpesaTransaction).filter(MpesaTransaction.status == "PENDING").order_by(MpesaTransaction.created_at.desc()).first()

        if transaction:
            transaction.status = "SUCCESS" if result_code == 0 else "FAILED"
            transaction.result_code = result_code
            transaction.result_desc = result_desc
            transaction.checkout_request_id = checkout_id
            transaction.completed_at = datetime.utcnow()
            db.commit()
            print(f"DEBUG: Transaction {transaction.id} updated.")
        else:
            print(f"DEBUG: CRITICAL - No transaction found for {checkout_id}")
    finally:
        db.close()

@router.post("/stkpush")
async def initiate_stk_push(
    body: STKPushRequest,
    x_auth_token: str = Header(...),
    db: Session = Depends(get_db)
):
    # 1. Signature Check
    if not verify_raw_signature(body.device_id, body.timestamp, x_auth_token):
        raise HTTPException(status_code=403, detail="Invalid request signature.")

    # 2. License Validation
    valid_license = db.query(License).filter(License.license_key == body.device_id).first()
    if not valid_license:
        raise HTTPException(status_code=404, detail="License key not found.")

    # 3. Persist PENDING transaction
    new_txn = MpesaTransaction(
        license_key=body.device_id,
        phone_number=str(body.phone_number),
        amount=body.amount,
        status="PENDING"
    )
    db.add(new_txn)
    try:
        db.commit()
        db.refresh(new_txn)
    except Exception as e:
        db.rollback()
        print(f"DEBUG: Database commit error: {e}")
        raise HTTPException(status_code=500, detail="Database write failed")

    # 4. Trigger M-Pesa STK Push
    access_token = get_mpesa_access_token()
    response = trigger_stk_push(
        db=db,
        phone_number=body.phone_number,
        amount=body.amount,
        license_key=body.device_id,
        account_reference=body.device_id,
        access_token=access_token
    )

    # 5. Save CheckoutRequestID
    resp_data = response.json()
    checkout_id = resp_data.get("CheckoutRequestID")
    if checkout_id:
        new_txn.checkout_request_id = checkout_id
        db.commit()
        print(f"DEBUG: Linked {checkout_id} to txn {new_txn.id}")

    return resp_data

@router.post("/callback")
async def mpesa_callback(request: Request, bg_tasks: BackgroundTasks):
    await verify_safaricom_ip(request)
    data = await request.json()
    bg_tasks.add_task(process_callback_data, data)
    return {"ResultCode": 0, "ResultDesc": "Accepted"}
