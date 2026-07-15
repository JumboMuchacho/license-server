from fastapi import APIRouter, Depends, Request, Header, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from database import get_db, SessionLocal
from billing import MpesaTransaction
import models
import json
import logging
from datetime import datetime, timezone # Fix 3
from security_mpesa import verify_safaricom_ips as verify_safaricom_ip
from services.mpesa_stk import trigger_stk_push
from services.mpesa_auth import get_mpesa_access_token
from schemas import STKPushRequest
from slowapi import Limiter
from slowapi.util import get_remote_address

logger = logging.getLogger(__name__)

limiter = Limiter(key_func=get_remote_address)
router = APIRouter(prefix="/api/v1/mpesa")

def process_callback_data(data: dict):
    """Background task to update device token balance directly."""
    db = SessionLocal()
    try:
        stk_callback = data.get("Body", {}).get("stkCallback", {})
        checkout_id = stk_callback.get("CheckoutRequestID")
        result_code = stk_callback.get("ResultCode")
        result_desc = stk_callback.get("ResultDesc")

        txn = db.query(MpesaTransaction).filter_by(checkout_request_id=checkout_id).first()

        if not txn:
            logger.warning(f"No transaction found for {checkout_id}")
            return
        if txn.status == "SUCCESS":
            logger.info(
                 "Duplicate callback ignored for %s",
                  checkout_id,
         )
         return

           # Save callback result details
    txn.result_code = result_code
    txn.result_desc = result_desc

    # Convert callback metadata into a dictionary for easier access
    metadata = stk_callback.get("CallbackMetadata", {}).get("Item", [])
    metadata_dict = {
        item["Name"]: item.get("Value")
        for item in metadata
        if "Name" in item
    }

    # Save M-Pesa receipt number
    txn.mpesa_receipt_number = metadata_dict.get("MpesaReceiptNumber")

    # Save completion time
    transaction_date = metadata_dict.get("TransactionDate")
    if transaction_date:
        txn.completed_at = datetime.strptime(
            str(transaction_date),
            "%Y%m%d%H%M%S",
        ).replace(tzinfo=timezone.utc)
    else:
        # Fallback to the current server time if Safaricom didn't provide one
        txn.completed_at = datetime.now(timezone.utc)

    # Amount paid
    amount = float(metadata_dict.get("Amount", 0))

    # Find the associated device
    device = (
        db.query(models.Device)
        .filter(models.Device.device_id == txn.device_id)
        .first()
    )
        if result_code == 0:
            txn.status = "SUCCESS"
            if device:
                tokens = int(amount / 10)
                device.token_balance += tokens
                # Fix 6: Detailed logging
                logger.info(
                        "Payment successful | Checkout=%s | Receipt=%s | Amount=KES %.0f | Tokens=%d | User=%s | Balance=%d",
                        checkout_id,
                        receipt,
                        amount,
                        tokens,
                        device.device_id,
                        device.token_balance,
                    )
        else:
            txn.status = "FAILED"
            # Fix 5: Concise logging
            logger.info("Payment failed | Checkout=%s | Result=%s | Desc=%s", checkout_id, result_code, result_desc)

        db.commit()

    except Exception:
        logger.exception("Error processing callback.")
        db.rollback()
    finally:
        db.close()

@router.post("/stkpush")
@limiter.limit("5/minute")  # Protects your API from bot-loops slamming your Safaricom budget
async def initiate_stk_push(
    body: STKPushRequest,
    request: Request,
    db: Session = Depends(get_db)
):
    # --- SECURITY GATEKEEPER CHECK ---
    # Validate Device directly against the database instead of client-side signing
    device = db.query(models.Device).filter(models.Device.device_id == body.device_id).first()
    if not device:
        # If the device identity is malicious or completely unverified, block them instantly
        raise HTTPException(status_code=403, detail="Unauthorized Device Identity.")

    # --- SERVER SIDE PARSING & INPUT SANITIZATION ---
    try:
        clean_phone = int(str(body.phone_number).strip().replace("+", ""))
        clean_amount = int(body.amount)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid payload formatting data structure.")

    # --- TRIGGER M-PESA PIPELINE ---
    try:
        access_token = get_mpesa_access_token()
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"M-Pesa authentication failed: {str(e)}"
        )
    logger.info(f"Triggering STK for {clean_phone}")

    response = await trigger_stk_push(
        db=db,
        phone_number=clean_phone,
        amount=clean_amount,
        account_reference=device.device_id,
        access_token=access_token
    )

    logger.info(f"Safaricom HTTP Status: {response.status_code}")
    logger.info(f"Safaricom Response: {response.text}")

    if response.status_code != 200:
        raise HTTPException(
            status_code=502,
            detail=f"Safaricom returned HTTP {response.status_code}: {response.text}"
    )

    try:
        resp_data = response.json()
    except Exception:
        raise HTTPException(
            status_code=500,
            detail=f"Safaricom returned invalid JSON: {response.text}"
        )

    # --- HANDLE RESPONSE ---
    if "CheckoutRequestID" in resp_data:
        new_txn = MpesaTransaction(
            device_id=device.device_id,
            phone_number=str(clean_phone),
            amount=clean_amount,
            status="PENDING",
            checkout_request_id=resp_data.get("CheckoutRequestID")
        )
        db.add(new_txn)
        db.commit()
        return resp_data
    else:
        raise HTTPException(status_code=400, detail=f"Safaricom Error: {resp_data}")


@router.post("/callback")
async def mpesa_callback(
    request: Request,
    bg_tasks: BackgroundTasks
):
    try:
        # Verify callback source
        await verify_safaricom_ip(request)

        #logger.info(f"Headers: {dict(request.headers)}")

        data = await request.json()

        bg_tasks.add_task(process_callback_data, data)

        return {
            "ResultCode": 0,
            "ResultDesc": "Accepted"
        }

    except HTTPException:
        raise

    except Exception:
        logger.exception("Callback processing failed.")

        raise HTTPException(
            status_code=500,
            detail="Callback processing failed."
        )
