# InWork

[![Deploy InWork preview to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy?repo=https://github.com/zopair/inwork/tree/service-marketplace-v1)

**Arabic-first service marketplace connecting people who need a service with nearby independent workers and craftsmen.**

InWork is not a job-listing website. It has two primary roles:

- **Requester — أحتاج خدمة:** select a profession, describe the task, share the service location, and find nearby available workers.
- **Worker — أقدم خدمة:** create a professional profile, set availability and service location, receive matching requests, and accept one request at a time.

## Current implementation

- Single-source Arabic RTL mobile-first web client in `index.html`, served directly by FastAPI for same-origin preview and packaged by Android WebView.
- FastAPI backend with local SQLite for development and optional remote Turso (SQLite-compatible) persistence for stateless free hosting.
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

### Run with Docker Compose

```bash
cp .env.example .env
# Generate a token with `python -c "import secrets; print(secrets.token_urlsafe(32))"` and set it in `.env` before starting.
docker compose up --build -d
```

Open `http://localhost:8000`. The Compose volume persists SQLite at `/data/inwork.sqlite3`. For a public server, put the container behind HTTPS using an open-source reverse proxy/PaaS such as Coolify, Dokku, or CapRover; keep the volume mounted and never expose the database file directly.


```bash
cd backend
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
export INWORK_DB_PATH="$PWD/data/inwork.sqlite3"
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Open `index.html` through a local static server, enter the API URL, and register an account. Do not use the public GitHub Pages site as a production service until a persistent HTTPS API is configured.

## Free preview deployment

A Render Blueprint is provided in `render.yaml` for the `service-marketplace-v1` branch. It serves both the Arabic UI (`/`) and FastAPI routes from one Render web service, so browser sessions are same-origin and no API URL or cross-site cookie configuration is needed. Data is stored in Turso rather than Render's ephemeral filesystem. Render's free service sleeps after inactivity, so the first request may take about a minute to wake. This is a preview/testing arrangement, not a production SLA.

1. Create a free Turso database and obtain its database URL and auth token from [Turso](https://turso.tech/).
2. Click the **Deploy InWork preview to Render** button above (or open [Render Blueprint deployment](https://render.com/deploy?repo=https://github.com/zopair/inwork/tree/service-marketplace-v1)), connect your GitHub account, and review the Blueprint.
3. Set `TURSO_DATABASE_URL` and `TURSO_AUTH_TOKEN` when Render prompts for the unsynchronized secrets.
4. Keep `INWORK_ALLOWED_ORIGINS=https://zopair.github.io` and `INWORK_COOKIE_SAMESITE=none`; the blueprint sets these values.
5. Open the generated `onrender.com` service URL (the Blueprint names the service `inwork-preview`; the actual hostname is shown by Render). The web UI and API share the same origin; leave the optional API URL field empty. The Android WebView uses the fixed origin `https://inwork.local`, which is explicitly allowlisted; enter the Render service URL in the Android app's optional API URL field.
6. Use `INWORK_ADMIN_BOOTSTRAP_TOKEN` once to create the first admin, then remove that secret from the service environment.

Do not select Render Postgres for durable free storage: its free database expires after 30 days. Do not store SQLite files on a Render free web service; its filesystem is ephemeral.

## Required deployment configuration

- `INWORK_DB_PATH`: local persistent SQLite database path; back it up. Used only when `TURSO_DATABASE_URL` is not set.
- `TURSO_DATABASE_URL` and `TURSO_AUTH_TOKEN`: optional remote Turso connection. When configured, the API uses the official `turso-serverless` DB-API driver and ignores `INWORK_DB_PATH`.
- `INWORK_ALLOWED_ORIGINS`: exact comma-separated frontend origins. Never use wildcard origins with credentials.
- `INWORK_COOKIE_SAMESITE=none`: only when frontend and API are cross-site; requires HTTPS. Prefer same-origin deployment because browsers may block third-party cookies.
- `INWORK_ADMIN_BOOTSTRAP_TOKEN`: one-time random secret (24+ characters) for first administrator creation. Remove it from the environment after bootstrap.

The API initializes the schema on startup. Keep local database files and secrets out of Git. The remote Turso driver is beta; validate transaction and concurrency behavior on the hosted database before accepting real customer requests.

## Tests

```bash
cd backend
python -m unittest discover -v
```

Pull requests run backend integration/security tests and browser E2E checks. The separate Android workflow validates the application JavaScript and builds a debug APK on main/manual runs.

## Important limits

This is an active development branch, not a production-ready public service. Email/phone verification, password recovery, identity verification, push notifications, backups/restore drills, production hosting, and monitoring are not implemented. Email is currently a login identifier, not proof of identity. Public OSM tile servers do not provide a production SLA; follow their usage policy.

No payment gateway, paid API, paid map service, or mock service listings are included.
