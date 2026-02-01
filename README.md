🛡️ Professional Licensing Authority (Backend)
A production-grade FastAPI backend designed for high-security software distribution. This system handles cryptographic license verification, multi-device orchestration, and administrative lifecycle management via a secure OAuth2/Supabase control plane.

🏗️ System Architecture
The server acts as the central validation authority, utilizing a multi-layered security approach:

1. The Security Layer
PBKDF2 Key Derivation: Instead of global secrets, the server derives per-device HMAC keys using 100,000 iterations of PBKDF2 with a unique salt.

HMAC-SHA256 Signing: Ensures all issued tokens are tamper-proof and cryptographically bound to the hardware ID.

Identity Proxy: Administrative routes are secured via Supabase Service Role verification, ensuring only whitelisted emails can manage license data.

2. The Logic Engine
Sticky Device Binding: Automatically handles device registration and enforces strict max_devices limits.

Migration Logic: Intelligent handling for hardware upgrades; permits device migration only if the previous license association is dead/expired.

Stateless Verification: Issues signed tokens for offline client resiliency while maintaining centralized revocation control.

🔐 Production Auth Flow (Admin UI)
The administration panel implements a modern Zero-Trust authentication flow:

Identity Provider: Admin logs in via Google OAuth through the Supabase JS client.

Token Exchange: The Admin UI captures the access_token and includes it in the Authorization: Bearer header.

FastAPI Middleware: The server proxies the token to Supabase’s /auth/v1/user endpoint.

Authorization: The server cross-references the authenticated email against a restricted ADMIN_EMAILS whitelist before granting access to CRUD operations.

🛠️ API Reference
Client Verification
POST /verify

Intent: Validates hardware and license status.

Logic: Checks expiration, active status, and device limit.

Response: Returns a signed payload containing an expiry timestamp (exp).

Admin Management (Internal)
GET /admin/licenses — List all keys and connected device telemetry. POST /admin/licenses — Issue new dashed 16-character keys. DELETE /admin/licenses/{key} — Instant global revocation.

📦 Deployment & Setup
Environment Configuration
Code snippet
# Security
LICENSE_SECRET=your_pbkdf2_derivation_secret
TOKEN_TTL_HOURS=1

# Database
DATABASE_URL=postgresql://user:pass@host:port/db

# Supabase Auth
SUPABASE_URL=your_project_url
SUPABASE_SERVICE_KEY=your_service_role_key
ADMIN_EMAILS=admin@example.com,dev@example.com
Launching the Instance
Bash
# Optimized for Render/Production
uvicorn main:app --host 0.0.0.0 --port 10000
🗂️ Project Structure
Plaintext
├── main.py            # API Gateway & Uvicorn entry point
├── models.py          # SQLAlchemy relational schema
├── security.py        # PBKDF2 & HMAC cryptographic functions
├── auth.py            # Supabase JWT & Whitelist middleware
├── admin_routes.py    # RESTful License CRUD logic
├── database.py        # PostgreSQL/SQLite connection pooling
└── static/admin       # Secure Admin UI (HTML/JS)