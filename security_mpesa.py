import os
from fastapi import Request, HTTPException

# Read allowed callback IPs from the environment
# Example:
# MPESA_ALLOWED_IPS=196.201.212.127,196.201.214.200,196.201.214.201
SAFARICOM_IPS = {
    ip.strip()
    for ip in os.getenv("MPESA_ALLOWED_IPS", "").split(",")
    if ip.strip()
}


async def verify_safaricom_ips(request: Request):
    """
    Verifies that the callback originates from an allowed Safaricom IP.
    Works correctly behind Render's proxy.
    """

    forwarded_for = request.headers.get("x-forwarded-for")
    real_ip = request.headers.get("x-real-ip")

    # First IP in X-Forwarded-For is the original client
    client_ip = (
        forwarded_for.split(",")[0].strip()
        if forwarded_for
        else request.client.host
    )

    print("========== M-PESA CALLBACK ==========")
    print(f"Client IP      : {client_ip}")
    print(f"X-Forwarded-For: {forwarded_for}")
    print(f"X-Real-IP      : {real_ip}")
    print(f"Allowed IPs    : {sorted(SAFARICOM_IPS)}")
    print("=====================================")

    if client_ip not in SAFARICOM_IPS:
        print(f"❌ Blocked callback from unauthorized IP: {client_ip}")
        raise HTTPException(
            status_code=403,
            detail="Forbidden: Unauthorized IP"
        )

    print(f"✅ Callback accepted from {client_ip}")
    return True
