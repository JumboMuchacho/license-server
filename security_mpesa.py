import os

from fastapi import HTTPException, Request

# Official Safaricom Daraja callback IP ranges (verify on the Daraja portal periodically)
DEFAULT_SAFARICOM_IPS = [
    "196.201.214.200",
    "196.201.214.201",
    "196.201.212.129",
    "196.201.212.138",
    "196.201.212.136",
    "196.201.212.74",
    "196.201.212.69",
]


def _allowed_callback_ips() -> set[str]:
    extra = os.getenv("MPESA_CALLBACK_EXTRA_IPS", "")
    extras = {ip.strip() for ip in extra.split(",") if ip.strip()}
    return set(DEFAULT_SAFARICOM_IPS) | extras


async def verify_safaricom_ips(request: Request) -> bool:
    if os.getenv("MPESA_SKIP_IP_VERIFY", "").lower() in {"1", "true", "yes"}:
        return True

    forwarded_for = request.headers.get("x-forwarded-for")
    client_ip = (
        forwarded_for.split(",")[0].strip()
        if forwarded_for
        else (request.client.host if request.client else "")
    )

    if client_ip not in _allowed_callback_ips():
        raise HTTPException(status_code=403, detail="Forbidden: Unauthorized IP")
    return True
