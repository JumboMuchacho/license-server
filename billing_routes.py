from fastapi import APIRouter, Depends, Request, Header, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from database import get_db, SessionLocal
from billing import MpesaTransaction
import models
from security_mpesa import verify_safaricom_ips as verify_safaricom_ip
from services.mpesa_stk import trigger_stk_push
from services.mpesa_auth import get_mpesa_access_token
from schemas import STKPushRequest
from slowapi import Limiter
from slowapi.util import get_remote_address

# Initialize SlowAPI rate limiting to safeguard the payment endpoint from abuse
limiter = Limiter(key_func=get_remote_address)

router = APIRouter(prefix="/api/v1/mpesa")

def process_callback_data(data: dict):
    """Background task to update device token balance directly."""
    db = SessionLocal()
    try:
        stk_callback = data.get("Body", {}).get("stkCallback", {})
        checkout_id = stk_callback.get("CheckoutRequestID")
        result_code = stk_callback.get("ResultCode")

        txn = db.query(MpesaTransaction).filter_by(checkout_request_id=checkout_id).first()
        if not txn: return

        metadata = stk_callback.get("CallbackMetadata", {}).get("Item", [])
        amount = next((float(i["Value"]) for i in metadata if i["Name"] == "Amount"), 0)

        device = db.query(models.Device).filter(models.Device.device_id == txn.device_id).first()

        if device and result_code == 0:
            device.token_balance += int(amount / 10)
            txn.status = "SUCCESS"
            db.commit()
        elif result_code != 0:
            txn.status = "FAILED"
            db.commit()
    except Exception as e:
        print(f"Error in callback processing: {e}")
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
    print(f"DEBUG: Triggering STK for {clean_phone} with token {access_token[:10]}...")

    response = await trigger_stk_push(
        db=db,
        phone_number=clean_phone,
        amount=clean_amount,
        account_reference=device.device_id,
        access_token=access_token
    )

    print("Status:", response.status_code)
    print("Body:", response.text)

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
async def mpesa_callback(request: Request, bg_tasks: BackgroundTasks):
    try:
        await verify_safaricom_ip(request)
        data = await request.json()
        bg_tasks.add_task(process_callback_data, data)
        return {"ResultCode": 0, "ResultDesc": "Accepted"}
    except Exception as e:
        print(f"Callback security error: {e}")
        raise HTTPException(status_code=400, detail="Invalid request")
