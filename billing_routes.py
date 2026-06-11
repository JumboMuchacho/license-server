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
    """Background task to handle M-Pesa callback and update license tokens."""
    print(f"DEBUG: Background task started for payload: {data}")
    db = SessionLocal()
    try:
        stk_callback = data.get("Body", {}).get("stkCallback", {})
        checkout_id = stk_callback.get("CheckoutRequestID")
        result_code = stk_callback.get("ResultCode")
        result_desc = stk_callback.get("ResultDesc")

        # Extract amount from metadata if available (standard M-Pesa callback structure)
        metadata = stk_callback.get("CallbackMetadata", {}).get("Item", [])
        amount = 0
        for item in metadata:
            if item.get("Name") == "Amount":
                amount = item.get("Value", 0)

        # Update the transaction record
        transaction = db.query(MpesaTransaction).filter_by(checkout_request_id=checkout_id).first()
        if transaction:
            transaction.status = "SUCCESS" if result_code == 0 else "FAILED"
            transaction.result_code = result_code
            transaction.result_desc = result_desc
            transaction.completed_at = datetime.utcnow()

            # --- TOKEN UPDATE LOGIC ---
            if transaction.status == "SUCCESS":
                # Find the linked license
                lic = db.query(License).filter(License.license_key == transaction.license_key).first()
                if lic:
                    # Math: 1 token for every 100 KES (adjust as needed)
                    tokens_added = int(amount) // 100
                    lic.token_balance += tokens_added
                    print(f"DEBUG: Added {tokens_added} tokens to license {lic.license_key}. New balance: {lic.token_balance}")

            db.commit()
            print(f"DEBUG: Transaction {checkout_id} successfully updated to {transaction.status}")
        else:
            print(f"DEBUG: CRITICAL - No transaction found in DB for CheckoutRequestID: {checkout_id}")
    except Exception as e:
        db.rollback()
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
    try:
        new_txn = MpesaTransaction(
            license_key=valid_license.license_key,
            phone_number=str(body.phone_number),
            amount=body.amount,
            status="PENDING"
        )
        db.add(new_txn)
        db.commit()
        db.refresh(new_txn)
        print(f"DEBUG: Successfully wrote PENDING transaction to DB: {new_txn.id}")
    except Exception as e:
        db.rollback()
        print(f"DEBUG: DATABASE WRITE FAILED: {e}")
        raise HTTPException(status_code=500, detail="Transaction storage failed.")

    # 4. Trigger M-Pesa STK Push
    access_token = get_mpesa_access_token()
    response = trigger_stk_push(
        db=db,                          # Added this
        license_key=valid_license.license_key, # Added this
        phone_number=body.phone_number,
        amount=body.amount,
        account_reference=valid_license.license_key,
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
        db.commit()

    return resp_data

@router.post("/callback")
async def mpesa_callback(request: Request, bg_tasks: BackgroundTasks):
    print("DEBUG: Callback endpoint reached!")
    try:
        # Note: Disable this during local development if your IP isn't allowed
        await verify_safaricom_ip(request)
        data = await request.json()
        print(f"DEBUG: Data received: {data}")

        bg_tasks.add_task(process_callback_data, data)
        return {"ResultCode": 0, "ResultDesc": "Accepted"}
    except Exception as e:
        print(f"DEBUG: Callback validation failed: {e}")
        raise HTTPException(status_code=400, detail="Invalid request")
