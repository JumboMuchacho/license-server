# create_license.py
from sqlalchemy.orm import Session
from database import SessionLocal, Base, engine
import models

# 1️⃣ Ensure tables exist
Base.metadata.create_all(bind=engine)

# 2️⃣ Open a DB session
db: Session = SessionLocal()

# 3️⃣ Define a new license
new_license = models.License(
    license_key="ABC-123-XYZ",  # Replace with your license key
    max_devices=1,              # Max allowed devices
    active=True                 # Set to False to disable later
)

# 4️⃣ Add license to DB and commit
db.add(new_license)
db.commit()
db.close()

print("✅ License created successfully!")
