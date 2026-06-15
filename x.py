import hmac
import hashlib

# Constants from your security.py
SALT = b"popup_detector_v2_secure_salt_2024"
PBKDF2_ITERATIONS = 100_000
KEY_LENGTH = 32

def generate_header_token(device_id, timestamp):
    """Generates the X-Auth-Token using the device_id as the source of truth."""
    # 1. Derive the secret key
    derived_key = hashlib.pbkdf2_hmac(
        hash_name="sha256",
        password=device_id.encode("utf-8"),
        salt=SALT,
        iterations=PBKDF2_ITERATIONS,
        dklen=KEY_LENGTH,
    )

    # 2. Rebuild the message string (must match server format exactly)
    message = f"{device_id}:{timestamp}"

    # 3. Compute HMAC-SHA256 signature
    signature = hmac.new(
        derived_key,
        message.encode("utf-8"),
        hashlib.sha256
    ).hexdigest()

    return signature

# --- SET YOUR TEST DATA HERE ---
# Use the actual device_id string you are using for registration
my_device_id = "YOUR_DEVICE_ID_HERE"
my_timestamp = 1781517010 # Ensure this matches the timestamp in your request body

token = generate_header_token(my_device_id, my_timestamp)
print(f"HEADER x-auth-token: {token}")
