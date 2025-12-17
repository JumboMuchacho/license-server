# license-server
simple made licensing server for automania.

## Admin UI

An admin web UI is available at `/admin` (served from `static/admin.html`).

- Admin token (simple placeholder): `SUPER_SECRET_ADMIN_TOKEN` (pass via the `token` query param in the UI).
- Endpoints:
	- `GET /admin/licenses?token=...` — list licenses
	- `POST /admin/licenses?token=...` — create a new license (JSON: `max_devices`, `days`, `active`)
	- `POST /admin/licenses/{license_key}/revoke?token=...` — revoke (deactivate)
	- `POST /admin/licenses/{license_key}/reactivate?token=...` — reactivate
	- `DELETE /admin/licenses/{license_key}?token=...` — delete license

The UI can create, list, revoke, reactivate and delete licenses.
