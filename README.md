# 🛡️ Taptap Backend Server
![Security Scan](https://img.shields.io/badge/Security-Authenticated-red.
svg)
![FastAPI](https://img.shields.io/badge/Framework-FastAPI-009688.svg)
![Supabase](https://img.shields.io/badge/Auth-Supabase-3ECF8E.svg)

FastAPI backend for the **Taptap Chrome extension**: device registration, token billing, M-Pesa top-ups, XPath rule delivery, and an admin control plane.

---

## Architecture

```text
Chrome Extension (MV3)
  ├── background.js   → HMAC-signed API calls, dynamic content-script registration
  ├── content.js      → DOM monitoring + token consumption triggers
  └── popup.js        → Balance UI + M-Pesa STK initiation

license-server (FastAPI)
  ├── main.py           → Client API (register, status, rules, consume)
  ├── billing_routes.py → M-Pesa STK + Safaricom callback
  ├── admin_routes.py   → Device CRUD + analytics (Supabase OAuth)
  ├── security.py       → PBKDF2 + HMAC request authentication
  └── auth.py           → Supabase JWT validation + admin email whitelist
```

### 🛡️ Security model

| Actor | Authentication | Notes |
|-------|----------------|-------|
| Extension client | HMAC-SHA256 (`X-Auth-Token`) + 5-minute timestamp window | Per-device key derived via PBKDF2 |
| Admin UI | Supabase Google OAuth + `ADMIN_EMAILS` whitelist | Bearer JWT validated server-side |
| M-Pesa callback | Safaricom IP allowlist | Optional dev bypass via env |

All client endpoints require signed requests except `/health` and `/admin/config` (public Supabase anon key only).

---

## 🔐 Environment variables

```env
# Core
ENV=production
SECRET_SALT=your_shared_pbkdf2_salt
DATABASE_URL=postgresql://...

# Admin auth
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SERVICE_KEY=your_service_role_key
SUPABASE_ANON_KEY=your_anon_key
ADMIN_EMAILS=admin@example.com

# CORS (comma-separated; extension fetch bypasses CORS via host_permissions)
ALLOWED_ORIGINS=https://origin address...

# Client config
CONTENT_SCRIPT_MATCHES=https://your-target-site.com/*,http://localhost/*
DETECTION_RULES="Your custom detection Rules//"]

# M-Pesa
MPESA_BASE_URL=https://api.safaricom.co.ke
MPESA_CONSUMER_KEY=
MPESA_CONSUMER_SECRET=
MPESA_SHORTCODE=
MPESA_PASSKEY=
MPESA_CALLBACK_URL=https://your-server.url.com/api/v1/mpesa/callback
# MPESA_CALLBACK_EXTRA_IPS=1.2.3.4   # dev only
# MPESA_SKIP_IP_VERIFY=true          # local testing only
```

---

## 🛠️ API reference

### Client (signed)

| Method | Path | Purpose |
|--------|------|---------|
| `POST` | `/api/v1/register` | Register or refresh a device |
| `POST` | `/api/v1/status` | Read token balance |
| `POST` | `/api/v1/config` | Return allowed content-script URL patterns |
| `POST` | `/api/v1/rules` | Return XPath rules (requires balance > 0) |
| `POST` | `/api/v1/billing/consume-token` | Decrement balance by 1 |
| `POST` | `/api/v1/mpesa/stkpush` | Initiate M-Pesa STK push |

**Signature:** `HMAC-SHA256(PBKDF2(device_id, SECRET_SALT), "{device_id}:{timestamp}")` sent as `X-Auth-Token`.

### Admin (Bearer JWT)

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/admin/devices` | List devices |
| `PATCH` | `/admin/devices/{id}` | Adjust token balance |
| `DELETE` | `/admin/devices/{id}` | Delete device |
| `GET` | `/admin/analytics` | Revenue and growth stats |
| `POST` | `/admin/reset-analytics` | Wipe transactions and zero balances |

---

## 📦 Deployment checklist

1. Set all env vars (especially `SECRET_SALT`, `ADMIN_EMAILS`, `DATABASE_URL_*`).
2. Set `MPESA_BASE_URL=https://api.safaricom.co.ke` for production M-Pesa.
3. Set `CONTENT_SCRIPT_MATCHES` to your production target domain(s).
4. Add the production target domain to the extension `manifest.json` `host_permissions` before Chrome Web Store submission.
5. Ensure `SECRET_SALT` in env vars matches the salt baked into the extension build.
6. Remove `MPESA_SKIP_IP_VERIFY` and test IPs from production.

---

## 🏗️ Local development

```bash
pip install -r requirements.txt
uvicorn main:app --reload --host 0.0.0.0 --port 10000
```

Open `/admin-ui` for the dashboard. API docs are available at `/docs` when `ENV` is not `production`.

---

## Extension integration notes

- The extension registers content scripts dynamically via `/api/v1/config` instead of injecting on all URLs.
- Balance polling goes through the background service worker (`GET_STATUS` message), not direct unauthenticated HTTP.
- On install/update, the extension signs and calls `/api/v1/register` automatically.

---

## Support

- **Lead Developer:** Job brian
- **Status:** Active maintenance
