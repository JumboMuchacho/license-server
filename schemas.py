from pydantic import BaseModel

class RegistrationSchema(BaseModel):
    device_id: str

class STKPushRequest(BaseModel):
    device_id: str
    phone_number: str
    tokens: int

class ConsumeTokenRequest(BaseModel):
    device_id: str
    txn_id: str
