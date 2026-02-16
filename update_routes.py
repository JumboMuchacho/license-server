import json
from fastapi import APIRouter, Request, HTTPException, Depends
from sqlalchemy.orm import Session

from database import get_db
from models import UpdateManifest
from security import verify_signature

router = APIRouter(tags=["Updates"])


@router.post("/update-manifest")
async def update_manifest(req: Request, db: Session = Depends(get_db)):
    body = await req.json()
    sig = req.headers.get("X-Signature")

    if not sig or not verify_signature(body, sig):
        raise HTTPException(status_code=403, detail="Invalid signature")

    manifest = (
        db.query(UpdateManifest)
        .order_by(UpdateManifest.updated_at.desc())
        .first()
    )

    if not manifest:
        raise HTTPException(status_code=404, detail="No update manifest configured")

    return {
        "latest_version": manifest.latest_version,
        "min_required_version": manifest.min_required_version,
        "mandatory": manifest.mandatory,
        "url": manifest.url,
        "sha256": manifest.sha256,
    }
