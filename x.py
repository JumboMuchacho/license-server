import base64
from datetime import datetime
import os
from dotenv import load_dotenv

# USE YOUR .env VALUES HERE FOR TESTING
shortcode = os.getenv("MPESA_SHORTCODE")
passkey = os.getenv("MPESA_PASSKEY")
timestamp = datetime.now().strftime('%Y%m%d%H%M%S')

# 1. Test Password Generation
data_to_encode = f"{shortcode}{passkey}{timestamp}"
encoded = base64.b64encode(data_to_encode.encode()).decode()
print(f"Generated Password: {encoded}")

# 2. Verify Credentials
print(f"Checking Shortcode: {shortcode}")
print(f"Checking Passkey Length: {len(passkey) if passkey else 0}")
