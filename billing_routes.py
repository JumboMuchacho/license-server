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

        metadata = stk_callback.get("CallbackMetadata", {}).get("Item", [])
        amount = 0.0
        for item in metadata:
            if item.get("Name") == "Amount":
                amount = float(item.get("Value", 0))

        transaction = db.query(MpesaTransaction).filter_by(checkout_request_id=checkout_id).first()

        if transaction:
            transaction.status = "SUCCESS" if result_code == 0 else "FAILED"
            transaction.completed_at = datetime.utcnow()

            if transaction.status == "SUCCESS":
                lic = db.query(License).filter(License.license_key == transaction.license_key).first()
                if lic:
                    tokens_added = int(amount // 100)
                    if tokens_added > 0:
                        lic.token_balance += tokens_added
                        print(f"DEBUG: Added {tokens_added} tokens. New balance: {lic.token_balance}")

            db.commit()
            if 'lic' in locals() and lic:
                db.refresh(lic)
        else:
            print(f"DEBUG: CRITICAL - No transaction found for {checkout_id}")

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
    if not verify_raw_signature(body.device_id, body.timestamp, x_auth_token):
        raise HTTPException(status_code=403, detail="Invalid request signature.")

    valid_license = db.query(License).filter(License.license_key == body.device_id).first()
    if not valid_license:
        raise HTTPException(status_code=404, detail="License key not found.")

    # 1. Trigger M-Pesa STK Push FIRST
    access_token = get_mpesa_access_token()
    response = trigger_stk_push(
        db=db,
        license_key=valid_license.license_key,
        phone_number=body.phone_number,
        amount=body.amount,
        account_reference=valid_license.license_key,
        access_token=access_token
    )

    # 2. Only create DB record if API request was accepted
    resp_data = response.json()
    checkout_id = resp_data.get("CheckoutRequestID")

    if checkout_id:
        try:
            new_txn = MpesaTransaction(
                license_key=valid_license.license_key,
                phone_number=str(body.phone_number),
                amount=body.amount,
                status="PENDING",
                checkout_request_id=checkout_id
            )
            db.add(new_txn)
            db.commit()
            print(f"DEBUG: Successfully wrote PENDING transaction: {checkout_id}")
        except Exception as e:
            db.rollback()
            raise HTTPException(status_code=500, detail="Transaction storage failed.")
    else:
        # Handle cases where M-Pesa rejects the request
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
