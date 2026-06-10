from fastapi import APIRouter, Depends, Request, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from database import get_db
from billing import MpesaTransaction
from security_mpesa import verify_safaricom_ip
from datetime import datetime

router = APIRouter(prefix="/api/v1/mpesa")

def process_callback_data(db: Session, data: dict):
    stk_callback = data.get("Body", {}).get("stkCallback", {})
    checkout_id = stk_callback.get("CheckoutRequestID")
    result_code = stk_callback.get("ResultCode")

    transaction = db.query(MpesaTransaction).filter_by(checkout_request_id=checkout_id).first()
    if transaction:
        transaction.status = "SUCCESS" if result_code == 0 else "FAILED"
        transaction.completed_at = datetime.utcnow()
        db.commit()

@router.post("/callback")
async def mpesa_callback(request: Request, bg_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    await verify_safaricom_ip(request)
    data = await request.json()

    # Process asynchronously to return 200 OK immediately
    bg_tasks.add_task(process_callback_data, db, data)

    return {"ResultCode": 0, "ResultDesc": "Accepted"}
