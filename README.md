# InWork

**Arabic-first service marketplace connecting people who need a service with nearby independent workers and craftsmen.**

InWork is not a job-listing website. It has two primary roles:

- **Requester — أحتاج خدمة:** select a profession, describe the task, share the service location, and find nearby available workers.
- **Worker — أقدم خدمة:** create a professional profile, set availability and service location, receive matching requests, and accept one request at a time.

## Current implementation

- Single-source Arabic RTL mobile-first web client in `index.html`, used by GitHub Pages and Android WebView.
- FastAPI backend with SQLite persistence.
- Password authentication, server-side revocable sessions, HttpOnly cookies, role-based authorization, login/signup throttling, and same-origin/allowlisted-origin write protection.
- Dynamic admin-managed categories.
- Worker profile and geospatial discovery using a bounded latitude/longitude search plus Haversine distance.
- Service request lifecycle: open → accepted → in_progress → completed; requester can cancel an open request.
- Atomic request acceptance; two workers cannot claim the same request.
- Worker subscription requests at 100 EGP, activated manually by an administrator for 30 days.
- Phone/WhatsApp private by default; requester consent is required before either party can retrieve contact details.
- Approximate worker map coordinates only; exact stored coordinates are not exposed by the public discovery endpoint.
- Leaflet 1.9.4 + OpenStreetMap tiles with attribution.

## Local backend

```bash
cd backend
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
export INWORK_DB_PATH="$PWD/data/inwork.sqlite3"
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Open `index.html` through a local static server, enter the API URL, and register an account. Do not use the public GitHub Pages site as a production service until a persistent HTTPS API is configured.

## Required deployment configuration

- `INWORK_DB_PATH`: persistent SQLite database path; back it up.
- `INWORK_ALLOWED_ORIGINS`: exact comma-separated frontend origins. Never use wildcard origins with credentials.
- `INWORK_COOKIE_SAMESITE=none`: only when frontend and API are cross-site; requires HTTPS. Prefer same-origin deployment because browsers may block third-party cookies.
- `INWORK_ADMIN_BOOTSTRAP_TOKEN`: one-time random secret (24+ characters) for first administrator creation. Remove it from the environment after bootstrap.

The API initializes the schema on startup. Keep local database files and secrets out of Git.

## Tests

```bash
cd backend
python -m unittest discover -v
```

Pull requests run backend integration/security tests and browser E2E checks. The separate Android workflow validates the application JavaScript and builds a debug APK on main/manual runs.

## Important limits

This is an active development branch, not a production-ready public service. Email/phone verification, password recovery, identity verification, push notifications, backups/restore drills, production hosting, and monitoring are not implemented. Email is currently a login identifier, not proof of identity. Public OSM tile servers do not provide a production SLA; follow their usage policy.

No payment gateway, paid API, paid map service, or mock service listings are included.
