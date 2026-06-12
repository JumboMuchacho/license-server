from pydantic import BaseModel

class RegistrationSchema(BaseModel):
    device_id: str

class STKPushRequest(BaseModel):
    device_id: str
    phone_number: int
    amount: int
    # Timestamp is good practice for replay protection
    timestamp: int
