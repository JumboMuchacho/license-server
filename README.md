# 💳 License Server: Token-Based Billing System

![FastAPI](https://img.shields.io/badge/Framework-FastAPI-009688.svg)
![Supabase](https://img.shields.io/badge/Auth-Supabase-3ECF8E.svg)
![M-Pesa](https://img.shields.io/badge/Payment-M--Pesa-green.svg)

A production-grade **FastAPI** backend for the Taptap browser extension, providing device registration, token-based billing, and M-Pesa STK push payment integration. The system serves as the central authority for cryptographic device authentication, token consumption tracking, and administrative management.

---

## 🏗️ System Architecture

The server acts as the "Single Source of Truth" for device entitlements, utilizing multi-layered security to prevent unauthorized access and token fraud.

### Server Responsibilities
- **Device Registration**: UUID-based device identification and lifecycle management
- **Token Management**: Balance tracking, consumption, and M-Pesa top-up integration
- **Payment Processing**: M-Pesa STK push initiation and callback handling
- **Admin Operations**: Device management, analytics, and balance adjustments via secure dashboard

### Security Layer
- **PBKDF2 Key Derivation**: Per-device HMAC keys derived using 100,000 iterations of PBKDF2-SHA256 with server-side salt
- **HMAC-SHA256 Signing**: All client requests signed with device-specific keys for tamper-proof authentication
- **Timestamp Validation**: 5-minute request window to prevent replay attacks
- **IP Whitelisting**: M-Pesa callbacks restricted to official Safaricom IP ranges
- **Rate Limiting**: SlowAPI middleware on all critical endpoints
- **Supabase Auth**: Admin routes protected via OAuth + email whitelist verification

### Logic Engine
- **Device Binding**: Automatic registration with UUID-based device identification
- **Token Consumption**: Atomic balance decrements with signature verification
- **Payment Integration**: M-Pesa STK push with automatic balance crediting on success
- **Stateless Verification**: Request-based authentication without session persistence

---

## 📂 Project Structure

```text
.
├── main.py                 # API Gateway, endpoints, and middleware
├── models.py               # SQLAlchemy Device model
├── security.py             # PBKDF2 key derivation & HMAC verification
├── security_mpesa.py       # M-Pesa IP whitelist validation
├── auth.py                 # Supabase JWT verification for admin routes
├── database.py             # PostgreSQL connection pooling & session management
├── billing.py              # MpesaTransaction model
├── billing_routes.py       # M-Pesa STK push and callback endpoints
├── admin_routes.py         # Admin device management and analytics
├── schemas.py              # Pydantic request/response schemas
├── services/
│   ├── mpesa_auth.py       # M-Pesa OAuth token caching
│   └── mpesa_stk.py        # STK push request builder
├── alembic/                # Database migration scripts
└── static/admin/           # Admin UI (HTML/JS)
```

---

## 🔐 Authentication Flow

### Client Authentication
1. **Device Registration**: Client generates UUID via `crypto.randomUUID()` and registers via `/api/v1/register`
2. **Key Derivation**: Server derives device-specific HMAC key using PBKDF2(device_id + SECRET_SALT)
3. **Request Signing**: Client signs requests with HMAC(device_id:timestamp) using derived key
4. **Server Verification**: Server recomputes signature and validates timestamp window

### Admin Authentication
1. **Identity Provider**: Admin authenticates via Google OAuth through Supabase
2. **Token Exchange**: Admin UI captures `access_token` and sends in `Authorization: Bearer` header
3. **FastAPI Middleware**: Server proxies JWT to Supabase `/auth/v1/user` for validation
4. **Authorization**: Server cross-references email against `ADMIN_EMAILS` whitelist

---

## 🛠️ API Reference

### Public Endpoints

#### `POST /api/v1/register`
Registers a new device or updates existing device timestamp.
- **Body**: `{"device_id": "uuid"}`
- **Response**: `{"status": "success", "device_id": "uuid", "token_balance": 0}`

#### `GET /api/v1/status`
Retrieves current token balance for a device.
- **Query**: `device_id=uuid`
- **Response**: `{"token_balance": 10, "is_active": true}`

#### `POST /api/v1/rules`
Fetches monitoring rules (XPath selectors) for content detection.
- **Headers**: `X-Auth-Token: hmac_signature`
- **Body**: `{"device_id": "uuid", "timestamp": 1234567890}`
- **Response**: `{"isActive": true, "rules": ["xpath_selector"]}`

#### `POST /api/v1/billing/consume-token`
Consumes one token from device balance (called when alert is triggered).
- **Headers**: `X-Auth-Token: hmac_signature`
- **Body**: `{"device_id": "uuid", "timestamp": 1234567890}`
- **Response**: `{"status": "authorized"}` or `410` if device not found

### M-Pesa Endpoints

#### `POST /api/v1/mpesa/stkpush`
Initiates M-Pesa STK push payment for token top-up.
- **Headers**: `X-Auth-Token: hmac_signature`
- **Body**: `{"device_id": "uuid", "phone_number": 2547..., "amount": 100, "timestamp": 1234567890}`
- **Response**: Safaricom STK push response with `CheckoutRequestID`

#### `POST /api/v1/mpesa/callback`
Handles M-Pesa payment callback (IP-restricted to Safaricom).
- **Body**: M-Pesa callback JSON with transaction result
- **Response**: `{"ResultCode": 0, "ResultDesc": "Accepted"}`

### Admin Endpoints (Protected)

#### `GET /admin/devices`
Retrieves all registered devices with balances and status.
- **Auth**: Requires valid Supabase JWT + admin email
- **Response**: Array of device objects

#### `PATCH /admin/devices/{device_id}`
Adjusts token balance for a specific device.
- **Auth**: Requires valid Supabase JWT + admin email
- **Body**: `{"token_adjustment": 10}`
- **Response**: `{"new_balance": 20}`

#### `DELETE /admin/devices/{device_id}`
Deletes a device from registry.
- **Auth**: Requires valid Supabase JWT + admin email
- **Response**: `{"status": "deleted"}`

#### `GET /admin/analytics`
Retrieves revenue, transaction counts, and growth metrics.
- **Auth**: Requires valid Supabase JWT + admin email
- **Response**: Analytics data object

#### `POST /admin/reset-analytics`
Resets all transactions and device balances (use with caution).
- **Auth**: Requires valid Supabase JWT + admin email
- **Response**: `{"status": "success"}`

---

## 📦 Deployment & Setup

### Environment Configuration (`.env`)

```env
# Security
SECRET_SALT=your_pbkdf2_salt_string
ENV=production

# Database (Supabase PostgreSQL)
DATABASE_URL=postgresql://user:pass@host:6543/db

# Supabase Auth
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SERVICE_KEY=your_service_role_key
ADMIN_EMAILS=admin@example.com,dev@example.com

# M-Pesa Daraja API
MPESA_CONSUMER_KEY=your_consumer_key
MPESA_CONSUMER_SECRET=your_consumer_secret
MPESA_SHORTCODE=174379
MPESA_PASSKEY=your_passkey
MPESA_CALLBACK_URL=https://your-server.com/api/v1/mpesa/callback
```

### Database Setup

```bash
# Initialize database tables
python create_tables.py

# Run migrations
alembic upgrade head
```

### Launching the Server

```bash
# Install dependencies
pip install -r requirements.txt

# Development
uvicorn main:app --reload

# Production (Render/VPS)
uvicorn main:app --host 0.0.0.0 --port 10000
```

---

## 🔒 Security Considerations

### Critical Security Notes
- **Remove Test IP**: Delete `129.222.147.141` from `security_mpesa.py` before production
- **Restrict CORS**: Replace wildcard CORS with specific Chrome extension ID
- **Protect Secrets**: Never commit `.env` file or expose `SECRET_SALT`
- **Monitor Logs**: Remove debug `print()` statements exposing sensitive data
- **Rate Limiting**: Adjust rate limits based on traffic patterns

### Recommended Improvements
- Add database row locking to prevent token race conditions
- Implement idempotency keys for STK push requests
- Add input validation for phone numbers and amounts
- Implement certificate pinning for M-Pesa API calls
- Add request signing to device registration endpoint

---

## 📞 Support & Maintenance

- **Developer**: Job Brian
- **Status**: 🟢 Active Production
- **Client Integration**: Taptap 3.0 Chrome Extension
- **Payment Provider**: Safaricom M-Pesa Daraja API
