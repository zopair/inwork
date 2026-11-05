# InWork service marketplace — API and security setup

## Product direction

The active application is now the requester/worker service marketplace. The former job-opportunity demo is no longer the main web or Android entry point.

## Local backend

From `backend/`:

```bash
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
export INWORK_DB_PATH="$PWD/data/inwork.sqlite3"
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

The API initializes the SQLite schema on startup. Keep `backend/data/` out of Git. For a first local test, open the web client and set its API URL to `http://localhost:8000`. Public deployments must use HTTPS.

## Frontend/API connection

The browser client is `index.html`; `mobile/index.html` is kept byte-for-byte aligned for the Pages build. Android packages the root `index.html`. The API URL is configured in the UI and stored locally as a non-secret setting.

For a separate HTTPS frontend origin, configure these backend environment variables:

- `INWORK_ALLOWED_ORIGINS`: comma-separated exact origins, e.g. `https://zopair.github.io`. Never use `*` with credentialed requests.
- `INWORK_COOKIE_SAMESITE=none`: required only when the frontend and API are cross-site. HTTPS is then mandatory.
- `INWORK_DB_PATH`: persistent SQLite file path.
- `INWORK_ADMIN_BOOTSTRAP_TOKEN`: one-time random secret, at least 24 characters, used to create the first administrator.

Prefer serving the API behind the same origin as the frontend. Some browsers block third-party cookies even with `SameSite=None`; if the frontend is on GitHub Pages and the API is on a different site, browser cookie policy may prevent login persistence. A same-site reverse proxy or same-origin hosting is the safer arrangement.

## Authentication and authorization

- Passwords are PBKDF2-HMAC-SHA256 hashes (310,000 rounds, random 16-byte salts); plaintext passwords are never stored.
- Sessions are random opaque tokens in HttpOnly cookies; only SHA-256 token digests are stored server-side.
- Session lifetime is seven days; logout revokes the server-side session.
- Cookie is HttpOnly and SameSite Strict by default; Secure is enabled on HTTPS.
- Registration accepts requester or worker only. Admin cannot self-register.
- Registration is limited to five attempts per client IP per hour. Login is limited to five failures per email/IP pair per 15 minutes.
- Unsafe API calls require `X-InWork-Request: 1` and a same-origin or explicitly allowlisted Origin.
- Roles are enforced server-side on requester, worker, and admin operations.
- First administrator creation is disabled unless `INWORK_ADMIN_BOOTSTRAP_TOKEN` is configured; bootstrap is one-time.

The email address is currently an account identifier, not a verified identity. Email OTP, phone OTP, ID/selfie checks, password reset, and account recovery are not implemented. Do not describe accounts as identity-verified.

## API surface

- `POST /v1/auth/register`, `POST /v1/auth/login`, `GET /v1/auth/me`, `POST /v1/auth/logout`
- `GET /v1/categories`
- `POST /v1/requests`, `GET /v1/requests/mine`, `POST /v1/requests/{id}/cancel`
- `GET /v1/workers/search?category_id=&latitude=&longitude=&radius_km=`
- `PUT /v1/worker/profile`, `GET /v1/worker/requests`
- `POST /v1/requests/{id}/accept`, `POST /v1/requests/{id}/status`, `POST /v1/requests/{id}/review`
- `POST /v1/requests/{id}/share-contact`, `GET /v1/requests/{id}/contact`
- `POST /v1/worker/subscription`, `GET /v1/admin/subscriptions/pending`, `POST /v1/admin/subscriptions/{id}/verify`
- `POST /v1/admin/bootstrap`, `POST /v1/admin/categories`

Worker discovery is requester-authenticated and returns approximate coordinates (rounded to two decimal places) and distance rounded to whole kilometers, not exact stored coordinates. A worker must be within 25 km of a request to accept it. Phone/WhatsApp fields are private and are returned only to the parties on an accepted/in-progress/completed request after requester consent.

## Subscription operations

A worker can create a pending subscription request for 100 EGP. An administrator manually verifies receipt outside the app, then calls the protected verify endpoint. Verification activates the subscription for 30 days and records an admin audit entry. No payment gateway or payment credentials are collected.

## Map and external dependencies

The client uses Leaflet 1.9.4 and OpenStreetMap tiles. Keep visible attribution and follow the public tile service usage policy. The public tile servers are not a guaranteed production SLA; for larger usage, choose a compliant tile provider or self-host tiles rather than scraping or bulk-prefetching.

## Tests

```bash
cd backend
python -m unittest discover -v
```

The backend suite covers password/session behavior, role gates, request lifecycle, concurrent acceptance, geospatial privacy, and contact disclosure. Browser E2E tests cover the Arabic marketplace entry and registration UI. Android APK compilation is validated by the separate Android workflow.

## Production blockers / not yet claimed

- No email/phone verification, password reset, or verified identity flow.
- No HTTPS backend deployment or persistent production database provisioned by this repository.
- No migration framework, backups, operational monitoring, or restore drill.
- No request negotiation/offers ledger yet; price negotiation remains a direct agreement and is not yet represented as an in-app bid workflow.
- No push notifications; workers currently poll/refresh the request feed.
- Browser cookie behavior across GitHub Pages and a different API site must be tested on target Android browsers.
