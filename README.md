![Security Scan](https://github.com/JumboMuchacho/license-server/actions/workflows/security.yml/badge.svg)
# License-server
A production-ready Python licensing and device management system built with **FastAPI** and **SQLAlchemy**. This server enables software monetization by managing license keys, enforcing device limits (Hardware-ID locking), and providing a streamlined integration client.  

## 🚀 Core Features

* **RESTful API:** Full CRUD operations for license management.
* **Device Locking:** Enforces `max_devices` per license to prevent unauthorized sharing.
* **Admin Dashboard:** Minimalist UI served at `/admin` for rapid management.
* **Integration Helper:** Client-side logic for offline grace periods and periodic re-validation.
* **Database Flexibility:** SQLAlchemy backend with automated SQLite migrations and environment-based configuration.

---

## 🛠️ Quick Start

### 1. Installation & Execution
```bash
# Install dependencies (assuming fastapi, uvicorn, sqlalchemy are in requirements.txt)
pip install -r requirements.txt

# Start the server
uvicorn main:app --reload
```
## Admin Authentication
The server uses HTTP Basic Auth. Configure your credentials via environment variables:
- ADMIN_USER (Default: admin)
- ADMIN_PASSWORD (Default: SUPER_SECRET_ADMIN_TOKEN)

## Usage Examples
Create a License
```bash
curl -u admin:SUPER_SECRET_ADMIN_TOKEN -X POST "[http://127.0.0.1:8000/admin/licenses](http://127.0.0.1:8000/admin/licenses)" \
     -H "Content-Type: application/json" \
     -d '{"max_devices":2, "days":30, "active":true}'
```
Verify a license(Client-side)
```bash
curl -X POST "[http://127.0.0.1:8000/verify](http://127.0.0.1:8000/verify)" \
     -H "Content-Type: application/json" \
     -d '{"license_key":"YOUR_KEY", "machine_id":"DEVICE_01"}'
```
## 📡 API Reference
### Architecture
Server
 ├─ /verify
 │   ├─ validates license
 │   ├─ enforces min_client_version
 │   ├─ enforces device limits
 │   └─ returns signed offline token
 │
Client
 ├─ verifies server response
 ├─ validates HMAC token
 ├─ allows offline only until expiry
 └─ forces recheck after TTL

### Admin API Endpoints

| Endpoint | Method | Action |
| :--- | :---: | :--- |
| `/admin/licenses` | **POST** | Create a new license |
| `/admin/licenses` | **GET** | List all licenses |
| `/admin/licenses/{key}/revoke` | **POST** | Disable a license |
| `/admin/licenses/{key}/reactivate` | **POST** | Re-enable a license |
| `/admin/licenses/{key}` | **DELETE** | Remove a license from DB |

### Client API Endpoints

| Endpoint | Method | Action |
| :--- | :---: | :--- |
| `/verify` | **POST** | Validate license & register `machine_id` |

## 🔌 Client Integration (poptest)
The poptest_license.py helper simplifies adding licensing to your applications:
- Validation Logic: Automatically prompts for keys on first run and stores them in OS config paths (e.g., %APPDATA% or ~/.config).
- Offline Policy: Supports a configurable "Offline Grace Period" (Default: 3 days) if the server is unreachable.
- Implementation:
```bash
from poptest_license import ensure_valid

if not ensure_valid("[https://your-server.com](https://your-server.com)", recheck_hours=24, offline_days=7):
    print("License invalid. Exiting.")
    sys.exit(1)
 ```
## 📝 Technical Notes
- Migrations: On startup, the system automatically applies migrations (e.g., adding expires_at columns) to existing SQLite databases.
- Date Format: All expiration dates are processed and displayed as YYYY/MM/DD.
- Deployment: Fully compatible with Railway, Render, or any Linux-based VPS. Ensure DATABASE_URL is set in production.
