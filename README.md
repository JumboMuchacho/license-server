# license-server
a simple made .py n' railway licensing server by yours truly. Me.Jbee

## Admin UI

A minimal admin panel is available at `/admin` and served from `static/admin.html`.

-- Admin auth: HTTP Basic (set env vars `ADMIN_USER` and `ADMIN_PASSWORD`). Defaults: `admin` / `SUPER_SECRET_ADMIN_TOKEN`.
	- `POST /admin/licenses` — create a license (JSON body: `max_devices`, `days`, `active`).
	- `GET /admin/licenses` — list licenses.
	- `POST /admin/licenses/{license_key}/revoke` — revoke (set active=false).
	- `POST /admin/licenses/{license_key}/reactivate` — reactivate.
	- `DELETE /admin/licenses/{license_key}` — delete license.

## Quick smoke test

1. Start server:

```bash
uvicorn main:app --reload
```

2. Create a license (HTTP Basic):

```bash
curl -u admin:SUPER_SECRET_ADMIN_TOKEN -X POST "http://127.0.0.1:8000/admin/licenses" \
	-H "Content-Type: application/json" \
	-d '{"max_devices":2,"days":30,"active":true}'
```

3. Verify license for device:

```bash
curl -X POST "http://127.0.0.1:8000/verify" -H "Content-Type: application/json" -d '{"license_key":"<LICENSE_KEY>","machine_id":"M1"}'
```

Replace `<LICENSE_KEY>` with the created key from step 2. The server will register devices up to `max_devices` and return 403 when the limit is reached.

To change admin credentials, set environment variables before starting the server:

```bash
export ADMIN_USER=myuser
export ADMIN_PASSWORD=mysecret
uvicorn main:app --reload
```

## Notes
- This project uses a very simple admin auth — replace with real auth before production.
- A minimal sqlite migration adds `expires_at` to the `licenses` table on startup.

## Date format

`expires_at` is now presented as: `YYYY/MM/DD` — example: `2025/12/17`.

## Run & Flow (how it runs and when)

- Start the server:

```bash
uvicorn main:app --reload
```

- What runs on startup:
	- SQLAlchemy creates missing tables via `models.Base.metadata.create_all(bind=engine)`.
	- A small migration helper `apply_pending_migrations()` will add the `expires_at` column to existing sqlite DBs if missing.

- Typical admin flow (what happens when you use the admin UI or API):
	1. Admin authenticates using HTTP Basic (`ADMIN_USER` / `ADMIN_PASSWORD`).
	2. Admin creates a license via `POST /admin/licenses` with JSON body `{ "max_devices": <n>, "days": <d>, "active": <true|false> }`.
		 - Server generates a random `license_key`, stores `max_devices`, `active`, and `expires_at = now + days` in the DB.
		 - Response contains `license_key` and `expires_at` formatted as `YYYYMMDD (hh:mm AM/PM)`.
	3. Clients call `POST /verify` with `{ "license_key": "...", "device_id": "..." }` or `machine_id`.
		 - Server looks up the license; if not found or not `active` or expired, returns 403.
		 - If device is new and the current registered device count is < `max_devices`, server registers the device and returns 200.
		 - If device is new and count >= `max_devices`, server returns 403 (device limit reached).
	4. Admin can `revoke`, `reactivate`, or `delete` licenses via admin endpoints or the admin UI; these change DB state immediately.

## Example timeline

- t=0: Admin creates license with `days=30` → DB stores `expires_at = now + 30 days`.
- t=1..n: Clients verify; server registers devices until `max_devices` reached.
- When `expires_at` passes, `verify` will reject (the code currently checks `active` only; you can extend verify to check expiry too if desired).

## Integrating with poptest (Selenium automator)

I added a helper module `poptest_license.py` to make integrating licensing into your `poptest` app straightforward.

Files added:
- `poptest_license.py` — helper to store/activate/ensure license validity with occasional rechecks and offline grace.
- `client.py` — updated with `verify_license()` which returns structured results for programmatic use.

Recommended integration steps (quick):

1. Copy `poptest_license.py` and `client.py` into `Desktop/mula/poptest` (or import them from this project if you make it a package).

2. On poptest startup (before launching Selenium), call:

```python
from poptest_license import ensure_valid

SERVER = 'https://your-license-server.example'  # use HTTPS in production
if not ensure_valid(SERVER, app_dir=None, recheck_hours=24, offline_days=0):
	print('License invalid or expired. Exiting.')
	sys.exit(1)

# proceed to initialize Selenium and run poptest
```

3. First-run activation UX:
   - Users can run `python poptest_license.py --activate --server http://yourserver` to enter their license key and activate/store it locally.
   - Alternatively, poptest can prompt on first-run by calling `ensure_valid(...)` which will prompt and save automatically.

Storage location:
- By default the helper saves `license.json` under the OS config path (Windows `%APPDATA%/poptest/license.json`, Linux `~/.config/poptest/license.json`).
- If you prefer storing the license inside the poptest folder, pass `app_dir='/path/to/poptest'` to `ensure_valid()` and activation functions; that will store `license.json` in that folder.

Policy implemented:
- Prompt for license on first run.
- Re-check with server every `recheck_hours` (default 24).
- If server cannot be reached, allow offline for up to `offline_days` (default 7) since last successful check.

Security notes:
- Use HTTPS for `SERVER` in production.
- Consider using OS keyring for storing secrets if you need stronger protection.



