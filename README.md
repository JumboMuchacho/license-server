# License Server

![Security Scan](https://github.com/JumboMuchacho/license-server/actions/workflows/security.yml/badge.svg)

A production-grade **FastAPI licensing server** providing secure license verification, device locking, and offline token issuance for distributed software.

---

## 🚀 Core Features

- License key verification
- Device-based locking (per-license limits)
- Signed offline tokens (HMAC)
- Expiration enforcement
- PostgreSQL / SQLite support
- Admin-protected management endpoints

---

## 🧠 Architecture Overview

###  Client(Windows Executable)
├─ Registration: Sends license_key + device_id to server
├─ Security: Verifies HMAC signature of server response
├─ Persistence: Stores signed token locally in hidden cache
└─ Resiliency: Works offline until token expiration

###  Server(FastAPI+PostgreSQL)
├─ Endpoint: Secure /verify route for activations
├─ Validation: Enforces max_devices per license key
├─ Issuance: Generates cryptographically signed tokens
└─ Management: Centralized revocation & expiration control


---

## 🛠 Setup

### Environment Variables

```env
LICENSE_SECRET=super_secure_secret
DATABASE_URL=postgresql://...
#ADMIN_USERNAME=admin  
#ADMIN_PASSWORD=strong_password

## ▶ Run Server

```bash
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 10000
```
## 🔑 Verify License (Client Call)
```bash
POST /verify
{
  "license_key": "XXXX-XXXX-XXXX",
  "device_id": "hashed_device_id"
}

**Response:**
```bash
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 10000

```
## 🔐 Security Model
- Server-only secrets
- HMAC-SHA256 signing
- Device-bound licenses
- Token expiration enforced
- Revocation effective immediately on recheck

## 📦 Deployment
Copatible with:
* REnder
* Railway
* Supabase Postgres 
* VPS/Docker

## 🔐 Auth Architecture (Clean & Correct)
In Production:
Layer	Responsibility
Browser (Admin UI)	Login with Supabase JS, store session
Supabase	Google OAuth, token issuance, refresh
FastAPI	Verify JWT via /auth/v1/user
Database	Trusts FastAPI only

## 🧩 Final Production Flow
Admin opens /admin-ui
Clicks Sign in with Google
Supabase JS redirects → Google → back
Supabase JS stores session
Admin UI reads session.access_token
API calls include:
Authorization: Bearer <access_token>
FastAPI verifies token via Supabase
Admin routes unlock