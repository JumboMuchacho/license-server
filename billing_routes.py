from fastapi import APIRouter, Depends, Request, Header, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from database import get_db, SessionLocal
from billing import (
    MpesaTransaction,
    calculate_amount,
)
import models
import json
import re
import logging
from datetime import datetime, timezone
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
    db = SessionLocal()

    try:
        stk_callback = data.get("Body", {}).get("stkCallback", {})
        checkout_id = stk_callback.get("CheckoutRequestID")
        result_code = stk_callback.get("ResultCode")
        result_desc = stk_callback.get("ResultDesc")

        txn = (
            db.query(MpesaTransaction)
            .filter_by(checkout_request_id=checkout_id)
            .first()
        )

        if not txn:
            logger.warning("No transaction found for %s", checkout_id)
            return

        if txn.status == "SUCCESS":
            logger.info("Duplicate callback ignored for %s", checkout_id)
            return

        txn.result_code = result_code
        txn.result_desc = result_desc

        metadata = stk_callback.get("CallbackMetadata", {}).get("Item", [])
        metadata_dict = {
            item["Name"]: item.get("Value")
            for item in metadata
            if "Name" in item
        }

        txn.mpesa_receipt_number = metadata_dict.get("MpesaReceiptNumber")

        transaction_date = metadata_dict.get("TransactionDate")

        if transaction_date:
            txn.completed_at = datetime.strptime(
                str(transaction_date),
                "%Y%m%d%H%M%S",
            ).replace(tzinfo=timezone.utc)
        else:
            txn.completed_at = datetime.utcnow()

        amount = int(float(metadata_dict.get("Amount", 0)))

        if result_code == 0:
            if amount != txn.amount:
                txn.status = "FAILED"
                txn.result_desc = (
                    f"Amount mismatch. Expected {txn.amount}, got {amount}"
                )

                logger.warning(
                    "Amount mismatch for %s. Expected %s, got %s",
                    checkout_id,
                    txn.amount,
                    amount,
                )

                db.commit()
                return

            device = (
                db.query(models.Device)
                .filter(models.Device.device_id == txn.device_id)
                .first()
            )

            txn.status = "SUCCESS"

            if not device:
                logger.warning(
                    "Device %s not found for successful transaction %s",
                    txn.device_id,
                    checkout_id,
                )
            else:
                device.token_balance += txn.tokens

                logger.info(
                    "Payment successful | Checkout=%s | Receipt=%s | Amount=KES %.0f | Tokens=%d | User=%s | Balance=%d",
                    checkout_id,
                    txn.mpesa_receipt_number,
                    amount,
                    txn.tokens,
                    device.device_id,
                    device.token_balance,
                )

        else:
            txn.status = "FAILED"

            logger.info(
                "Payment failed | Checkout=%s | Result=%s | Desc=%s",
                checkout_id,
                result_code,
                result_desc,
            )

        db.commit()

    except Exception:
        logger.exception("Error processing callback.")
        db.rollback()

    finally:
        db.close()

@router.post("/stkpush")
@limiter.limit("5/minute")
async def initiate_stk_push(
    body: STKPushRequest,
    request: Request,
    db: Session = Depends(get_db)
):
    device = db.query(models.Device).filter(models.Device.device_id == body.device_id).first()
    if not device:
        raise HTTPException(status_code=403, detail="Unauthorized Device Identity.")

    try:
        clean_phone = str(body.phone_number).strip().replace(" ", "").replace("-", "").replace("+", "")
        clean_tokens = int(body.tokens)
    except (ValueError, TypeError):
        raise HTTPException(
            status_code=400,
            detail="Invalid payload."
        )

    # Validate the final format
    if not re.fullmatch(r"254(7|1)\d{8}", clean_phone):
        raise HTTPException(
            status_code=400,
            detail="Enter a valid Kenyan phone number."
        )

    ALLOWED_TOKEN_PACKAGES = {1, 2, 5, 10, 20, 40, 80, 160, 320, 640}

    if clean_tokens not in ALLOWED_TOKEN_PACKAGES:
        raise HTTPException(
            status_code=400,
            detail="Invalid token package."
        )

    clean_amount = int(calculate_amount(clean_tokens))

    logger.info(
        "TOKEN_PRICE=%s | Tokens=%s | Amount=%s",
        TOKEN_PRICE,
        clean_tokens,
        clean_amount,
    )

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

    if response.status_code != 200:
        raise HTTPException(
            status_code=502,
            detail=f"Safaricom returned HTTP {response.status_code}: {response.text}"
        )

    try:
        resp_data = response.json()

        logger.info(
            "STK request accepted | Checkout=%s",
            resp_data.get("CheckoutRequestID")
        )
    except Exception:
        raise HTTPException(
            status_code=500,
            detail=f"Safaricom returned invalid JSON: {response.text}"
        )

    if "CheckoutRequestID" in resp_data:
        new_txn = MpesaTransaction(
            device_id=device.device_id,
            phone_number=clean_phone,
            tokens=clean_tokens,
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
        await verify_safaricom_ip(request)

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
