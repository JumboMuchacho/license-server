from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from database import SessionLocal, engine
import models

models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="License Server")

class VerifyRequest(BaseModel):
    license_key: str
    device_id: str

@app.post("/verify")
def verify(req: VerifyRequest):
    db = SessionLocal()

    license = db.query(models.License).filter_by(
        license_key=req.license_key,
        active=True
    ).first()

    if not license:
        raise HTTPException(status_code=403, detail="Invalid license")

    device = db.query(models.Device).filter_by(
        license_id=license.id,
        device_id=req.device_id
    ).first()

    if device:
        return {"status": "ok"}

    devices_count = db.query(models.Device).filter_by(
        license_id=license.id
    ).count()

    if devices_count >= license.max_devices:
        raise HTTPException(status_code=403, detail="Device limit reached")

    new_device = models.Device(
        license_id=license.id,
        device_id=req.device_id
    )
    db.add(new_device)
    db.commit()

    return {"status": "ok"}
