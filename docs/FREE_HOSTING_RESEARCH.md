# InWork — infrastructure research, blockers, and execution plan

Research date: 2026-11-05

## Executive decision

Do not rewrite InWork around a new backend product yet. Keep the existing FastAPI domain/API and SQLite-compatible SQL. Add a selectable database adapter so local development stays on SQLite while a stateless preview can use Turso's remote SQL-over-HTTP driver. The first no-card preview candidate is a single same-origin FastAPI service on Render Free + Turso Free; it is a temporary public test environment, not a production SLA. For a durable self-hosted route, package the API for Docker and deploy it with an open-source PaaS on a machine/VM the owner controls.

## GitHub repositories reviewed

| Repository | What it provides | Fit for InWork | Decision |
|---|---|---|---|
| [tursodatabase/turso](https://github.com/tursodatabase/turso) | SQLite-compatible database engine and serverless SQL-over-HTTP Python driver | High: preserves most existing SQL and supports explicit transactions | Use optional `turso-serverless` adapter; hosted transaction behavior still needs live verification |
| [coollabsio/coolify](https://github.com/coollabsio/coolify) | Self-hosted PaaS for apps, databases, and Git deployments | High for an owned Linux VM | Keep as primary self-host control-plane candidate; it does not provide compute |
| [dokku/dokku](https://github.com/dokku/dokku) | Small Git-push PaaS using Docker/buildpacks | High for a small single-server API | Lean fallback if Coolify resource use is excessive |
| [caprover/caprover](https://github.com/caprover/caprover) | Docker Swarm + nginx app/database deployment UI | Medium | Alternative; more moving parts than needed for one API |
| [Dokploy/dokploy](https://github.com/Dokploy/dokploy) | Self-hosted Docker/Compose deployment platform | Medium | Alternative; still needs a server |
| [elliothux/open-compute](https://github.com/elliothux/open-compute) | Single-binary self-hosted Workers-compatible runtime with SQLite/object storage | Exploratory only: current backend is Python/FastAPI, not Workers code | Do not port the API yet; revisit if the backend is deliberately rewritten to Workers-compatible TypeScript |
| [trailbaseio/trailbase](https://github.com/trailbaseio/trailbase) | Rust single-executable backend with auth, geospatial and SQLite/Postgres support | Technically interesting but marked alpha and OSL-3.0 | Do not replace the current API; migration cost and license review outweigh benefits now |
| [pocketbase/pocketbase](https://github.com/pocketbase/pocketbase) | Go + SQLite backend | Old organization repository is archived/moved | Do not pin new deployment to the archived repository |
| [build996/actually-free-hosting](https://github.com/build996/actually-free-hosting) | Curated free-hosting matrix | Useful discovery index, not a hosting provider or authoritative contract | Use as a lead list only; verify provider terms directly |
| [awesome-selfhosted/awesome-selfhosted](https://github.com/awesome-selfhosted/awesome-selfhosted) | Curated free-software self-hosting catalog | Broad discovery source | Use for further alternatives, not as a runtime |

## Hosting candidates and real limitations

| Candidate | Cost/entry condition | Limitation | Verdict |
|---|---|---|---|
| Render Free Web Service | $0 preview tier; repo connection required | Sleeps after 15 minutes idle, cold start about one minute, ephemeral filesystem, 750 free instance-hours/workspace/month; free Render Postgres expires after 30 days | Suitable only with external durable DB; selected for a preview path |
| Turso Free | $0 and no card; 5 GB storage, 100 databases on the published free plan | Hosted vendor service; free quotas apply; remote driver is beta and requires real transaction tests | Selected as remote DB for preview because it is SQLite-compatible |
| Oracle Always Free VM | Always Free compute allocation; signup requires credit/debit card verification | Idle instances may be reclaimed; regional capacity can be unavailable | Optional self-hosted path only if owner accepts card verification and operational responsibility |
| Google Cloud E2-micro | Free allowance in specific US regions; billing account required | 1 GB/month outbound transfer, billing-account requirement, regional restrictions | Not selected |
| GitHub Actions runners | Included CI compute within GitHub quotas | Ephemeral jobs; no durable filesystem or always-on service guarantee | CI only; never use cron/keepalive loops as production hosting |

## Problems identified

1. GitHub Pages is static hosting; it cannot run the FastAPI process.
2. The current API uses local SQLite. Render Free loses local files on restart, redeploy, or idle spin-down.
3. Render's free Postgres is not a durable answer because the free database expires after 30 days.
4. Cross-origin cookies would be fragile between a static frontend and a separate API. The preview now avoids that by serving the frontend and API from the same FastAPI origin, with `SameSite=Strict` and trusted HTTPS proxy headers.
5. The current backend uses SQLite-specific connection setup, row factories, schema scripts, and explicit `BEGIN IMMEDIATE`; any remote adapter must preserve those semantics.
6. The free Render service may cold-start and has no production SLA. It is acceptable for a test preview, not a launch guarantee.
7. The admin bootstrap token and Turso URL/token must be supplied as secrets; the assistant cannot create third-party accounts or invent credentials.
8. Existing automated tests validate local SQLite behavior. They cannot prove remote Turso transaction isolation or hosted cookie behavior without a live database and service URL.
9. The current branch still has unimplemented production controls: email/phone verification, password reset, identity verification, monitoring, backup/restore drill, and push notifications.

## Execution checklist

- [x] Survey open-source PaaS, backend, database, and self-hosting repositories.
- [x] Verify provider constraints against official documentation instead of relying on free-tier roundup claims.
- [x] Keep local SQLite as the default development mode.
- [x] Add an optional remote Turso DB-API connection path.
- [x] Add a unit test for selecting the remote adapter and requiring its auth token.
- [x] Add a Render Blueprint for a same-origin UI + API preview, backed by remote Turso rather than ephemeral local files.
- [x] Add a portable Dockerfile and persistent Docker Compose volume for self-hosted Coolify/Dokku/CapRover deployment.
- [x] Add Docker image and Compose validation to CI.
- [x] Document the provider limits and fallback options.
- [ ] Run CI on the newest branch head and fix any regressions.
- [ ] Create the Turso database and place its URL/token into Render's secret fields.
- [ ] Connect the repository to Render and deploy the Blueprint.
- [ ] Open the Render service URL; same-origin API routing requires no extra frontend configuration.
- [ ] Verify `/health`, registration, login, logout, session persistence, worker profile, geospatial search, request lifecycle, and consent-gated contact.
- [ ] Run a two-worker acceptance race against the hosted database and verify exactly one winner.
- [ ] Verify data survives service sleep/restart and redeployment.
- [ ] Create a backup/export and perform a restore test before any real users.
- [ ] Decide whether the temporary preview is sufficient or move to a self-hosted VM + Coolify/Dokku for a more durable always-on service.

## Fallback ladder

1. Render Free + Turso Free for a quick no-card same-origin public preview.
2. If Render rejects the service or imposes unsuitable limits, run the same Dockerized API on a user-controlled Linux host using Dokku or Coolify; the app and DB remain portable.
3. If a free VM is acceptable and card verification is acceptable, test Oracle Always Free, but monitor reclaim conditions and maintain off-host backups.
4. If no public compute account is available, run the API locally on an always-on owner-controlled computer and use a secure tunnel only for temporary testing; never expose an unauthenticated database or leave an admin bootstrap secret active.

## Security and deployment rules

- Never store Turso credentials, admin bootstrap tokens, or user data in Git.
- Do not use a Render local SQLite file or its expiring free Postgres for persistent customer data.
- Do not claim production readiness from a green CI run alone.
- Do not keep free compute alive by artificial cron traffic or abuse provider quotas.
- Before real users, add backups, restore drills, rate-limit monitoring, identity/account recovery, and a documented incident path.

## Pages preview failure and replacement

The isolated GitHub Pages preview workflow was run and failed at `actions/configure-pages@v5` because the repository does not have a Pages site enabled/configured. Enabling Pages through that action requires a non-`GITHUB_TOKEN` credential with GitHub App `administration:write` and `pages:write` or an appropriate PAT. To avoid requesting elevated credentials or touching the existing Pages configuration, the failed preview workflow was removed. The preview now uses a single same-origin Render service that serves the HTML page and API together.
