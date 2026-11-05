# InWork service marketplace foundation

This branch starts the transition from job-opportunity discovery to the agreed requester/worker service marketplace. The existing job-discovery UI and API are left untouched for now so the working baseline is not silently broken.

## First implementation slice

- SQLite schema for users, admin-managed categories, worker profiles, service requests, manual subscriptions, reviews, identity-verification placeholders, and admin audit events.
- Request creation validates requester role, active account, active category, non-empty description, and coordinate bounds.
- Request acceptance uses a write transaction (`BEGIN IMMEDIATE`) and a conditional update requiring `status = 'open'` and `worker_id IS NULL`. A concurrent second worker receives `false`; it cannot overwrite the winner.
- A worker must be active, available, assigned to the request category, and have an active manually verified subscription before acceptance.
- Worker lifecycle transitions are restricted to the assigned worker: `accepted -> in_progress -> completed`.
- WhatsApp/contact fields are stored privately and are never selected or returned by the domain helpers.

## Local setup

The domain layer uses Python's standard-library `sqlite3`; no new runtime dependency is required.

From `backend/`:

```bash
python -c "from app.marketplace import initialize_database; initialize_database()"
python -m unittest test_smoke.py test_marketplace.py -v
```

Set `INWORK_DB_PATH` to choose a database file. By default the database is created at `backend/data/inwork.sqlite3` (the data directory should not be committed).

## Security boundary

This commit intentionally does **not** expose marketplace routes through FastAPI. The current application has no verified authentication/session layer. Adding public create/accept endpoints before identity and role enforcement would allow unauthenticated users to impersonate requesters or workers.

The next backend milestone is to implement and test authentication, session handling, role dependencies, requester cancellation, worker discovery by category and distance, and only then expose these domain operations as API routes. Public worker responses must exclude phone/WhatsApp and exact private coordinates. Contact disclosure should be a separate authorized operation after acceptance and explicit consent.

## Known limits of this slice

- No production authentication, API routes, map UI integration, or migration framework yet.
- SQLite is the low-resource MVP database; evaluate PostgreSQL/PostGIS only when deployment scale requires it.
- Subscription rows are intended to be activated by an authenticated admin after manual payment verification; no payment gateway is included.
