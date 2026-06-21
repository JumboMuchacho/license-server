from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from sqlalchemy.orm import Session

import models
from billing import MpesaTransaction
from database import SessionLocal, get_db
from schemas import STKPushRequest
from security import verify_device_request
from security_mpesa import verify_safaricom_ips as verify_safaricom_ip
from services.mpesa_auth import get_mpesa_access_token
from services.mpesa_stk import trigger_stk_push

router = APIRouter(prefix="/api/v1/mpesa")


def process_callback_data(data: dict):
    db = SessionLocal()
    try:
        stk_callback = data.get("Body", {}).get("stkCallback", {})
        checkout_id = stk_callback.get("CheckoutRequestID")
        result_code = stk_callback.get("ResultCode")

        txn = (
            db.query(MpesaTransaction)
            .filter_by(checkout_request_id=checkout_id)
            .first()
        )
        if not txn:
            return

        metadata = stk_callback.get("CallbackMetadata", {}).get("Item", [])
        amount = next((float(i["Value"]) for i in metadata if i["Name"] == "Amount"), 0)

        device = (
            db.query(models.Device)
            .filter(models.Device.device_id == txn.device_id)
            .first()
        )

        if device and result_code == 0:
            device.token_balance += int(amount / 10)
            txn.status = "SUCCESS"
            txn.result_code = result_code
            db.commit()
        elif result_code != 0:
            txn.status = "FAILED"
            txn.result_code = result_code
            db.commit()
    except Exception as e:
        print(f"Error in callback processing: {e}")
    finally:
        db.close()


@router.post("/stkpush")
async def initiate_stk_push(
    body: STKPushRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    x_auth_token = request.headers.get("x-auth-token") or request.headers.get(
        "X-Auth-Token"
    )
    if not x_auth_token:
        raise HTTPException(status_code=401, detail="Missing auth token.")

    verify_device_request(body.device_id, body.timestamp, x_auth_token)

    device = (
        db.query(models.Device)
        .filter(models.Device.device_id == body.device_id)
        .first()
    )
    if not device:
        raise HTTPException(status_code=404, detail="Device not registered.")
    if not device.active:
        raise HTTPException(status_code=403, detail="Device is suspended.")

    access_token = get_mpesa_access_token()
    response = trigger_stk_push(
        db=db,
        phone_number=str(body.phone_number),
        amount=body.amount,
        account_reference=device.device_id,
        access_token=access_token,
    )

    resp_data = response.json()
    if "CheckoutRequestID" in resp_data:
        new_txn = MpesaTransaction(
            device_id=device.device_id,
            phone_number=str(body.phone_number),
            amount=body.amount,
            status="PENDING",
            checkout_request_id=resp_data.get("CheckoutRequestID"),
        )
        db.add(new_txn)
        db.commit()
        return {
            "CheckoutRequestID": resp_data.get("CheckoutRequestID"),
            "status": "pending",
        }

    raise HTTPException(status_code=400, detail="Payment initiation failed.")


@router.post("/callback")
async def mpesa_callback(request: Request, bg_tasks: BackgroundTasks):
    try:
        await verify_safaricom_ip(request)
        data = await request.json()
        bg_tasks.add_task(process_callback_data, data)
        return {"ResultCode": 0, "ResultDesc": "Accepted"}
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid request")
