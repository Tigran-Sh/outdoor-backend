# Outdoor Backend

Backend for an Armenian outdoor experiences marketplace (hiking, running,
cycling, outdoor tours and other outdoor experiences).

This repository currently contains the **backend foundation**: project
setup, custom user model, authentication (JWT), a code-defined role /
capability authorization system, admin user-management APIs and API
documentation. Domain features (clubs, events, bookings, payments, etc.)
are intentionally **not** implemented yet.

## Technology stack

- Python 3.12+
- Django 5.1
- Django REST Framework
- PostgreSQL (via `DATABASE_URL`, `psycopg` 3)
- django-configurations
- djangorestframework-simplejwt (with token blacklist)
- drf-yasg (Swagger / ReDoc)
- django-cors-headers
- flake8
- Docker / Docker Compose

## Project structure

```
outdoor-backend/
├── manage.py
├── outdoor_backend/
│   ├── settings.py          # django-configurations classes
│   ├── schema.py            # drf-yasg schema view
│   ├── urls.py
│   ├── asgi.py
│   └── wsgi.py
├── apps/
│   ├── common/              # cross-domain building blocks
│   │   ├── models.py        # UUIDTimeStampedModel
│   │   ├── pagination.py    # DefaultPagination
│   │   ├── exceptions.py    # unified error envelope
│   │   └── api/
│   │       ├── views.py     # health endpoint
│   │       └── schema.py    # drf-yasg schema args
│   └── users/
│       ├── constants.py     # Role, Capability, ROLE_CAPABILITIES
│       ├── managers.py      # email-based UserManager
│       ├── models.py        # custom User model
│       ├── admin.py         # custom UserAdmin
│       ├── urls.py
│       ├── migrations/
│       ├── api/
│       │   ├── permissions.py
│       │   ├── serializers.py
│       │   ├── schema.py    # drf-yasg schema args (reused via **SCHEMA)
│       │   └── views.py
│       ├── services/
│       │   ├── authorization.py
│       │   └── catalog.py   # RoleCatalog / CapabilityCatalog
│       └── tests/           # role/permission + auth API test suite
├── scripts/
│   └── start.sh             # container entrypoint (collectstatic+migrate+gunicorn)
├── Dockerfile
├── docker-compose.yml
├── .env.example
├── .flake8
├── requirements.txt
└── README.md
```

## Configuration (django-configurations)

Settings live in `outdoor_backend/settings.py` as configuration classes
(no `settings/base.py` split). Select the active class with
`DJANGO_CONFIGURATION`.

- `BaseConf` — shared settings (apps, middleware, DRF, SIMPLE_JWT,
  database, `AUTH_USER_MODEL`, CORS, Swagger, logging, i18n, timezone).
- `LocalConf` — local development: `DEBUG=True`, insecure secret-key
  fallback, permissive local hosts/CORS, no forced HTTPS.
- `DevConf` — deployed dev/staging: `DEBUG` from env, proxy SSL header.
- `ProdConf` — production: `DEBUG=False`, `SECRET_KEY` **required** (no
  insecure fallback), HTTPS redirect, secure cookies and HSTS
  (all env-configurable).

Bootstrap (`manage.py`, `wsgi.py`, `asgi.py`) uses django-configurations,
so standard Django management commands work with:

```
DJANGO_SETTINGS_MODULE=outdoor_backend.settings
DJANGO_CONFIGURATION=LocalConf
```

## Environment variables

Copy the example file and adjust as needed:

```bash
cp .env.example .env
```

| Variable | Purpose |
| --- | --- |
| `DJANGO_SETTINGS_MODULE` | Always `outdoor_backend.settings` |
| `DJANGO_CONFIGURATION` | `LocalConf` / `DevConf` / `ProdConf` |
| `DJANGO_SECRET_KEY` | Secret key (required in Dev/Prod) |
| `DJANGO_DEBUG` | Debug flag |
| `DJANGO_ALLOWED_HOSTS` | Comma-separated allowed hosts |
| `DATABASE_URL` | PostgreSQL connection URL |
| `CORS_ALLOWED_ORIGINS` | Comma-separated allowed frontend origins |
| `JWT_ACCESS_TOKEN_LIFETIME_MINUTES` | Access token lifetime |
| `JWT_REFRESH_TOKEN_LIFETIME_DAYS` | Refresh token lifetime |
| `LOG_LEVEL` | Root log level (default `INFO`) |

`.env` is git-ignored and must never be committed. `.env.example`
contains no real secrets, and production has no insecure fallbacks.

## Make targets

Development is **Docker-only** — there is no local virtualenv. Every
Django/quality command runs inside the `web` container via
`docker compose run --rm web ...`, wrapped by the `Makefile`. Run
`make help` to list all targets:

| Target | Description |
| --- | --- |
| `make env` | Create `.env` from `.env.example` |
| `make up` / `make up-d` | Build & start the full stack (foreground / detached) |
| `make down` | Stop and remove containers |
| `make down-volumes` | Stop and drop volumes (destroys DB data) |
| `make build` | Build the web image |
| `make db-up` / `make db-down` | Start / stop only PostgreSQL |
| `make logs` / `make web-logs` | Tail all / web container logs |
| `make migrate` / `make migrations` | Apply / create migrations |
| `make superuser` | Create a superuser (Platform Admin) |
| `make check` / `make check-migrations` | Django checks / missing-migration check |
| `make test` | Run the test suite |
| `make lint` | Run flake8 |
| `make shell` | Open the Django shell |
| `make clean` | Remove Python caches |

Typical first run:

```bash
make env        # create .env
make up-d       # build & start web + postgres (migrations run on boot)
make superuser  # create a Platform Admin
```

## Local development

The full stack runs in Docker:

```bash
docker compose up --build
```

The `web` service waits for the `postgres` healthcheck, then runs
`scripts/start.sh` (collectstatic + migrate + gunicorn) on port `8000`.
The Django app is built by `Dockerfile` and served by gunicorn; static
assets (Swagger/ReDoc/admin) are served via WhiteNoise.

One-off management commands run through the `web` container, e.g.:

```bash
docker compose run --rm web python manage.py migrate
docker compose run --rm web python manage.py createsuperuser
```

### Create a superuser

```bash
make superuser
# or: docker compose run --rm web python manage.py createsuperuser
```

You will be prompted for `email`, `full_name` and password. Superusers
are created with `role=platform_admin`.

### Tests

```bash
make test
# a subset: make test ARGS="apps.users.tests.test_authorization"
```

### Lint

```bash
make lint
```

## API documentation

- Swagger UI: `http://localhost:8000/api/swagger/`
- ReDoc: `http://localhost:8000/api/redoc/`
- Raw schema: `http://localhost:8000/api/swagger.json`
- Health: `http://localhost:8000/api/health/`

Swagger is configured for JWT Bearer auth. Click **Authorize** and enter
`Bearer <access-token>`.

## Authentication flow (JWT)

1. `POST /api/v1/auth/login/` with `{ "email", "password" }` →
   `{ access, refresh, user }`.
2. Send `Authorization: Bearer <access>` on authenticated requests.
3. `POST /api/v1/auth/refresh/` with `{ "refresh" }` → new `access`.
4. `POST /api/v1/auth/logout/` with `{ "refresh" }` blacklists the token.
5. `GET /api/v1/auth/me/` returns the current user.
6. `POST /api/v1/auth/change-password/` with
   `{ "current_password", "new_password" }`.

Inactive users cannot authenticate. Login errors are generic to avoid
user enumeration.

There is intentionally **no public registration endpoint** yet. Users are
created via the protected admin API, Django admin, or `createsuperuser`.

## Admin APIs (Platform Admin only)

User management:

- `GET  /api/v1/admin/users/` (filters: `role`, `is_active`; search:
  `email`, `full_name`)
- `GET  /api/v1/admin/users/{id}/`
- `POST /api/v1/admin/users/`
- `PATCH /api/v1/admin/users/{id}/` (name/email only)
- `POST /api/v1/admin/users/{id}/activate/`
- `POST /api/v1/admin/users/{id}/deactivate/`
- `PATCH /api/v1/admin/users/{id}/role/` (dedicated role change)
- `PATCH /api/v1/admin/users/{id}/capabilities/` (assign capabilities;
  `internal_admin` users only)

Roles & capabilities (read-only, code-defined):

- `GET /api/v1/admin/roles/`
- `GET /api/v1/admin/roles/{role}/`
- `GET /api/v1/admin/roles/{role}/capabilities/`
- `GET /api/v1/admin/capabilities/`

## Roles

Business roles (`apps/users/constants.py`, stored on `User.role`):

| Key | Name |
| --- | --- |
| `participant` | Participant |
| `club_owner` | Club Owner |
| `guide` | Guide |
| `internal_admin` | Internal Admin |
| `platform_admin` | Platform Admin |

Business roles are **separate** from Django's `is_staff` / `is_superuser`
admin flags — do not conflate them.

### Internal Admin (custom permissions)

`internal_admin` is a staff role with **no default capabilities**. When a
user is set to this role you **must assign** them a capability subset,
which becomes their exact effective permission set. Assignment happens at
creation (`capabilities` in the create payload) or via
`PATCH /api/v1/admin/users/{id}/capabilities/`.

Guardrail: a requester can only grant capabilities they themselves hold,
so a Club Owner could never grant platform-governance capabilities
(`verify_club`, `suspend_club`, `issue_refund`) while a Platform Admin can
grant anything. Each created account records its creator via
`User.created_by`. Changing an internal admin's role to a fixed-capability
role clears the assigned capabilities.

## Capability model

Capabilities are fine-grained, API-friendly permission keys defined in
code:

`edit_club_profile`, `create_event`, `edit_event`, `publish_event`,
`view_participants`, `export_participants`, `qr_check_in`,
`confirm_completion`, `view_finances`, `manage_team_members`,
`cancel_event`, `request_refund`, `verify_club`, `suspend_club`,
`issue_refund`.

### Role → capability matrix

- **Participant** — none (marketplace-only for now).
- **Club Owner** — `edit_club_profile`, `create_event`, `edit_event`,
  `publish_event`, `view_participants`, `export_participants`,
  `qr_check_in`, `confirm_completion`, `view_finances`,
  `manage_team_members`, `cancel_event`, `request_refund`.
- **Guide** — `view_participants`, `export_participants`, `qr_check_in`,
  `confirm_completion`.
- **Internal Admin** — none by default; capabilities are assigned
  per user (see above).
- **Platform Admin** — all capabilities (platform-wide).

The default matrix lives in exactly one place: `ROLE_CAPABILITIES` in
`apps/users/constants.py`. A user's *effective* capabilities are computed
by `effective_capabilities(role, custom_capabilities)` = role defaults ∪
per-user assigned capabilities. It is defined in Python (no dynamic
database-backed RBAC at this stage).

## Authorization architecture

```
Authentication
      ↓
Role
      ↓
Capability
      ↓
Resource Scope
      ↓
ALLOW / DENY
```

- **Authentication / Role / Capability** are implemented now, in
  `apps/users/services/authorization.py` (`has_role`, `has_capability`,
  `is_admin_panel_user`, ...) and in the DRF permission classes
  (`IsClubOwner`, `IsGuide`, `IsPlatformAdmin`, `IsAdminPanelUser`,
  `IsClubOwnerOrPlatformAdmin`, `HasCapability`, ...).
- **Resource Scope** is domain-specific and deferred. Having a
  capability at the role level is **not** sufficient for scoped actions:
  - A **Guide**'s `qr_check_in` / `view_participants` will be limited to
    the events **assigned to that guide**.
  - A **Club Owner**'s capabilities will be limited to **their own
    club's** resources.
  - A **Platform Admin** is authorized **platform-wide**.

  These object-level checks (e.g. `can_manage_event`,
  `can_check_in_participant`) will live close to their domain
  (`apps/clubs`, `apps/events`) once those models exist. Extension points
  are documented in `apps/users/services/authorization.py`.

## Error format

API errors use a consistent envelope:

```json
{
  "error": {
    "code": "permission_denied",
    "message": "You do not have permission to perform this action."
  }
}
```

## Intentionally deferred

Clubs, club membership, events, bookings, payments, participant
registration, club-owner public onboarding, guide invitations,
guide-event assignment, participant lists, QR generation/scanning,
check-in / completion / refund / payout workflows, email, notifications,
AWS integrations, Redis, Celery, and automated tests are **out of scope**
for this task and belong to future work.
