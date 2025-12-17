# create_license.py
import random
import string
from datetime import datetime, timedelta
import argparse
from sqlalchemy.orm import Session
from database import SessionLocal, Base, engine
import models

# 1️⃣ Ensure tables exist
Base.metadata.create_all(bind=engine)

# 2️⃣ Function to generate random license key
def generate_license_key(length=12):
    chars = string.ascii_uppercase + string.digits
    return '-'.join(
        ''.join(random.choices(chars, k=4)) for _ in range(length // 4)
    )

# 3️⃣ Parse CLI arguments
parser = argparse.ArgumentParser(description="Create a new license")
parser.add_argument('--max_devices', type=int, default=1, help='Max allowed devices')
parser.add_argument('--days', type=int, default=365, help='License validity in days')
parser.add_argument('--active', type=bool, default=True, help='Set license active or inactive')
args = parser.parse_args()

# 4️⃣ Open DB session
db: Session = SessionLocal()

# 5️⃣ Create new license
new_license = models.License(
    license_key=generate_license_key(),
    max_devices=args.max_devices,
    active=args.active,
    expires_at=datetime.utcnow() + timedelta(days=args.days)
)

db.add(new_license)
db.commit()
db.close()

print(f"✅ License created: {new_license.license_key}")
