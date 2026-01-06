from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional
from database import SessionLocal, engine, apply_pending_migrations
import models
import admin_routes

models.Base.metadata.create_all(bind=engine)

# apply minimal migrations for existing DBs
apply_pending_migrations()

app = FastAPI(title="License Server")

# mount static files for admin UI
app.mount("/static", StaticFiles(directory="static"), name="static")

# include admin API routes
app.include_router(admin_routes.router)


class VerifyRequest(BaseModel):
    license_key: str
    # clients may send either `device_id` or `machine_id`
    device_id: Optional[str] = None
    machine_id: Optional[str] = None


@app.get("/")
def health():
    return {"status": "ok"}


@app.get("/admin")
def admin_ui():
    return FileResponse("static/admin.html")

@app.post("/verify")
def verify(req: VerifyRequest):
    db = SessionLocal()
    try:
        # First check if license exists at all (without active filter)
        license = db.query(models.License).filter_by(
            license_key=req.license_key.strip()
        ).first()

        if not license:
            db.close()
            raise HTTPException(status_code=403, detail="License key not found")

        # Check if license is active
        if not license.active:
            db.close()
            raise HTTPException(status_code=403, detail="License is inactive (revoked)")

        # check expiry if set
        if getattr(license, 'expires_at', None) is not None:
            import datetime as _dt
            if license.expires_at <= _dt.datetime.utcnow():
                db.close()
                raise HTTPException(status_code=403, detail="License expired")

        # accept either field for compatibility with existing clients
        device_identifier = req.device_id or req.machine_id
        if not device_identifier:
            db.close()
            raise HTTPException(status_code=400, detail="Missing device identifier")

        device = db.query(models.Device).filter_by(
            license_id=license.id,
            device_id=device_identifier
        ).first()

        if device:
            db.close()
            return {"status": "ok"}

        devices_count = db.query(models.Device).filter_by(
            license_id=license.id
        ).count()

        if devices_count >= license.max_devices:
            db.close()
            raise HTTPException(status_code=403, detail="Device limit reached")

        new_device = models.Device(
            license_id=license.id,
            device_id=device_identifier
        )
        db.add(new_device)
        db.commit()
        db.close()

        return {"status": "ok"}
    except HTTPException:
        # Re-raise HTTP exceptions
        db.close()
        raise
    except Exception as e:
        db.close()
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")
