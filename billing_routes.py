# Import the new service
from services.mpesa_stk import trigger_stk_push

@router.post("/stkpush")
async def initiate_stk_push(
    body: STKPushRequest,
    x_auth_token: str = Header(...),
    db: Session = Depends(get_db)
):
    # 1. Security Check
    if not verify_raw_signature(body.device_id, body.timestamp, x_auth_token):
        raise HTTPException(status_code=403, detail="Invalid request signature.")

    # 2. Get Token
    access_token = get_mpesa_access_token()

    # 3. Call Service
    response = trigger_stk_push(
        phone_number=body.phone_number,
        amount=body.amount,
        account_reference=body.device_id,
        access_token=access_token
    )

    return response.json()
