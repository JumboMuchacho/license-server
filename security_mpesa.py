# security_mpesa.py
from fastapi import Request, HTTPException

# Official Safaricom IP ranges (Verify these occasionally on the Daraja portal)
SAFARICOM_IPS = [
    "196.201.214.200", "196.201.214.201", "196.201.212.129",
    "196.201.212.138", "196.201.212.136", "196.201.212.74", "196.201.212.69",
    "129.222.187.156" # <--- ADDEDD YOUR CURRENT IP HERE FOR TESTING
]

async def verify_safaricom_ips(request: Request):
    # Use 'x-forwarded-for' because Render sits behind a proxy/load balancer
    forwarded_for = request.headers.get("x-forwarded-for")
    # The true client IP is usually the first in the comma-separated list
    client_ip = forwarded_for.split(",")[0].strip() if forwarded_for else request.client.host

    if client_ip not in SAFARICOM_IPS:
        print(f"Blocked callback attempt from unauthorized IP: {client_ip}")
        raise HTTPException(status_code=403, detail="Forbidden: Unauthorized IP")
    return True
