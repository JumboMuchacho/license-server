import sys
from database import SessionLocal
import models

def reset_bindings(license_key: str):
    db = SessionLocal()
    lic = db.query(models.License).filter_by(license_key=license_key).first()
    if not lic:
        print(f"License not found: {license_key}")
        db.close()
        return 2

    deleted = db.query(models.Device).filter_by(license_id=lic.id).delete()
    db.commit()
    db.close()
    print(f"Deleted {deleted} device(s) for license {license_key}")
    return 0


if __name__ == '__main__':
    key = 'ABC-123-XYZ'
    sys.exit(reset_bindings(key))
