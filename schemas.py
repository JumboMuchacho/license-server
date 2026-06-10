from pydantic import BaseModel

class STKPushRequest(BaseModel):
    device_id: str
    phone_number: int
    amount: int
    timestamp: int
