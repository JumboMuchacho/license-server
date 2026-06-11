import hmac
import hashlib
import binascii

# Constants from your security.py
SALT = b"popup_detector_v2_secure_salt_2024"
PBKDF2_ITERATIONS = 100_000
KEY_LENGTH = 32

def generate_header_token(device_id, timestamp):
    # 1. Derive the secret key (same as your server)
    derived_key = hashlib.pbkdf2_hmac(
        hash_name="sha256",
        password=device_id.encode("utf-8"),
        salt=SALT,
        iterations=PBKDF2_ITERATIONS,
        dklen=KEY_LENGTH,
    )

    # 2. Rebuild the message string
    message = f"{device_id}:{timestamp}"

    # 3. Compute HMAC-SHA256 signature
    signature = hmac.new(
        derived_key,
        message.encode("utf-8"),
        hashlib.sha256
    ).hexdigest()

    return signature

# --- SET YOUR TEST DATA HERE ---
my_license_key = "E5CB-E868-CEF9-456E"
my_timestamp = 1718045600 # Ensure this matches your JSON body exactly

token = generate_header_token(my_license_key, my_timestamp)
print(f"HEADER x-auth-token: {token}")
