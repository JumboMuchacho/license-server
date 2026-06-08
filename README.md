# 🛡️ License-server: Backend Control Plane

![Security Scan](https://img.shields.io/badge/Security-Authenticated-red.svg)
![FastAPI](https://img.shields.io/badge/Framework-FastAPI-009688.svg)
![Supabase](https://img.shields.io/badge/Auth-Supabase-3ECF8E.svg)

A production-grade **FastAPI** backend designed for high-security software entitlement. This system serves as the central authority for cryptographic license verification, multi-device orchestration, and administrative lifecycle management via a secure **Zero-Trust** control plane.



---

## 🏗️ System Architecture

The server acts as the "Single Source of Truth," utilizing a multi-layered security approach to prevent unauthorized access and license spoofing.
### Server responsibilities
- License validation
- Update manifest generation
- Mandatory update enforcement
- Admin UI toggles versions / uploads zips

### 1. The Security Layer
- **PBKDF2 Key Derivation:** To mitigate "Global Secret" vulnerabilities, the server derives unique, per-device HMAC keys using **100,000 iterations** of PBKDF2 with a unique cryptographic salt.
- **HMAC-SHA256 Signing:** Ensures all issued tokens are tamper-proof and cryptographically bound to the client's hardware fingerprint.
- **Identity Proxy:** Administrative routes are secured via **Supabase Service Role** verification, ensuring only whitelisted engineer emails can modify license data.

### 2. The Logic Engine
- **Sticky Device Binding:** Automatically handles registration and enforces strict `max_devices` concurrency limits.
- **Migration Logic:** Features intelligent handling for hardware upgrades; permits device migration only if the previous license association is verified as inactive or expired.
- **Stateless Verification:** Issues signed tokens for offline client resiliency while maintaining centralized revocation control.

---

## 🔐 Production Auth Flow (Admin UI)

The administration panel implements a modern **Zero-Trust** authentication architecture:

1.  **Identity Provider:** Admin authenticates via **Google OAuth** through the Supabase JS client.
2.  **Token Exchange:** The Admin UI captures the `access_token` and includes it in the `Authorization: Bearer` header for all API calls.
3.  **FastAPI Middleware:** The server proxies the JWT to Supabase’s `/auth/v1/user` endpoint for real-time validation.
4.  **Authorization:** The server cross-references the authenticated email against a restricted `ADMIN_EMAILS` whitelist before granting access to CRUD operations.



---

## 📂 Project Structure

```text
.
├── main.py            # API Gateway & Uvicorn entry point
├── models.py          # SQLAlchemy relational schema (Licenses/Devices)
├── security.py        # PBKDF2 & HMAC cryptographic functions
├── auth.py            # Supabase JWT & Whitelist middleware
├── admin_routes.py    # RESTful License CRUD logic
├── database.py        # PostgreSQL connection pooling & session management
└── static/admin       # Secure Admin UI (HTML/JS)

```

---

## 🛠️ API Reference
### Client Verification
**`POST /verify`**

* **Intent:** Validates hardware integrity and current license status.
* **Logic:** Executes a server-side check of expiration dates, activation status, and device affinity (binding).
* **Response:** Returns a cryptographically signed payload containing the session signature and an expiry timestamp (`exp`).

---

### Admin Management (Protected)
*These endpoints require a valid Supabase JWT and admin whitelist clearance.*

* **`GET /admin/licenses`** Retrieves a comprehensive list of all issued keys alongside real-time device telemetry and activation counts.

* **`POST /admin/licenses`** Generates and issues new 16-character dashed license keys with configurable device limits.

* **`DELETE /admin/licenses/{key}`** Triggers immediate global revocation of entitlements for a specific key, instantly deauthorizing all associated devices.

---

## 📦 Deployment & Setup

### Environment Configuration (`.env`)

To ensure the system operates correctly, create a `.env` file in the root directory with the following variables:

```env
# Security
LICENSE_SECRET=your_pbkdf2_derivation_secret

# Database
DATABASE_URL=postgresql://user:pass@host:port/db

# Supabase Auth
SUPABASE_URL=your_project_url
SUPABASE_SERVICE_KEY=your_service_role_key
ADMIN_EMAILS=admin@example.com,dev@example.com
```

---

### 🚀Launching the Instance

For local development or production VPS environments, use **Uvicorn** for a high-performance ASGI server:

```bash
# Optimized for Production (Render/VPS)
uvicorn main:app --host 0.0.0.0 --port 10000
---
```

## 📞 Support & Maintenance

- **Lead Developer:** Job brian
- **Status:** 🟢 Active Maintenance / Production Ready
