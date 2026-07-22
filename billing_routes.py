import re
# Amount paid
amount = float(metadata_dict.get("Amount", 0))

if result_code == 0:

    # Verify the callback amount matches what we expected
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

    # Associated device
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

    try:
        clean_phone = str(body.phone_number).strip().replace("+", "")
        clean_tokens = int(body.tokens)
    except (ValueError, TypeError):
        raise HTTPException(
            status_code=400,
            detail="Invalid payload."
        )

    # Validate phone number
    if not re.fullmatch(r"2547\d{8}", clean_phone):
        raise HTTPException(
            status_code=400,
            detail="Phone number must be in 2547XXXXXXXX format."
        )

    ALLOWED_TOKEN_PACKAGES = {5, 10, 20, 40, 80, 160, 320, 640}

    if clean_tokens not in ALLOWED_TOKEN_PACKAGES:
        raise HTTPException(
            status_code=400,
            detail="Invalid token package."
        )

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

    # --- HANDLE RESPONSE ---
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
