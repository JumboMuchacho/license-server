# Save this in the same directory as security.py
from security import derive_device_secret
import hmac
import hashlib

# YOUR TEST DATA
# Ensure these match the JSON body in Postman exactly
device_id = "test-device-123"
timestamp = 1718000000

# 1. Derive the key using the function from your security.py
secret = derive_device_secret(device_id)

# 2. Build the string exactly as verify_raw_signature does
message = f"{device_id}:{timestamp}".encode("utf-8")

# 3. Create the signature
signature = hmac.new(secret, message, hashlib.sha256).hexdigest()

print(f"--- POSTMAN CONFIGURATION ---")
print(f"HEADER [x-auth-token]: {signature}")
print(f"JSON BODY [device_id]: {device_id}")
print(f"JSON BODY [timestamp]: {timestamp}")
