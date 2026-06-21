from pydantic import BaseModel, Field


class RegistrationSchema(BaseModel):
    device_id: str
    timestamp: int


class StatusRequest(BaseModel):
    device_id: str
    timestamp: int


class STKPushRequest(BaseModel):
    device_id: str
    phone_number: int
    amount: int = Field(gt=0, le=500000)
    timestamp: int


class ConsumeTokenRequest(BaseModel):
    device_id: str
    timestamp: int
