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
    print(f"DEBUG: Background task started for payload: {data}")
    db = SessionLocal()
    try:
        stk_callback = data.get("Body", {}).get("stkCallback", {})
        checkout_id = stk_callback.get("CheckoutRequestID")
        result_code = stk_callback.get("ResultCode")
        result_desc = stk_callback.get("ResultDesc")

        # Update the transaction record
        transaction = db.query(MpesaTransaction).filter_by(checkout_request_id=checkout_id).first()
        if transaction:
            transaction.status = "SUCCESS" if result_code == 0 else "FAILED"
            transaction.result_code = result_code
            transaction.result_desc = result_desc
            transaction.completed_at = datetime.utcnow()
            db.commit()
            print(f"DEBUG: Transaction {checkout_id} successfully updated to {transaction.status}")
        else:
            print(f"DEBUG: CRITICAL - No transaction found in DB for CheckoutRequestID: {checkout_id}")
    except Exception as e:
        print(f"DEBUG: Error in background task: {e}")
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
        print(f"DEBUG: License key {body.device_id} not found.")
        raise HTTPException(status_code=404, detail="License key not found.")

    # 3. Create PENDING record
    new_txn = MpesaTransaction(
        license_key=body.device_id,
        phone_number=str(body.phone_number),
        amount=body.amount,
        status="PENDING"
    )
    db.add(new_txn)
    db.commit()
    db.refresh(new_txn)

    # 4. Trigger M-Pesa STK Push
    access_token = get_mpesa_access_token()
    response = trigger_stk_push(
        phone_number=body.phone_number,
        amount=body.amount,
        account_reference=body.device_id,
        access_token=access_token
    )

    # 5. Link CheckoutRequestID
    resp_data = response.json()
    checkout_id = resp_data.get("CheckoutRequestID")
    if checkout_id:
        new_txn.checkout_request_id = checkout_id
        db.commit()
        print(f"DEBUG: Created txn {new_txn.id} with CheckoutRequestID: {checkout_id}")
    else:
        new_txn.status = "FAILED"
        new_txn.result_desc = resp_data.get("errorMessage", "Unknown error")
        db.commit()

    return resp_data

@router.post("/callback")
async def mpesa_callback(request: Request, bg_tasks: BackgroundTasks):
    print("DEBUG: Callback endpoint reached!")
    try:
        await verify_safaricom_ip(request)
        data = await request.json()
        print(f"DEBUG: Data received: {data}")

        bg_tasks.add_task(process_callback_data, data)
        return {"ResultCode": 0, "ResultDesc": "Accepted"}
    except Exception as e:
        print(f"DEBUG: Callback validation failed: {e}")
        # Note: We return 200 to Safaricom even on error if we want to stop retries,
        # or 400 if we want them to retry.
        raise HTTPException(status_code=400, detail="Invalid request")
