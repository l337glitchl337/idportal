# Architecture

## Overview

IDPortal is a multi-container Flask application. All containers are defined in `docker-compose.yml` (production) and `docker-compose.test.yml` (test stack). The application source is baked into the Flask image at build time — there is no volume mount for code.

## Container layout

```
┌─────────────────────────────────────────────────────────────────┐
│  Host                                                           │
│                                                                 │
│  :8080 (HTTP)  :8443 (HTTPS)  :8025 (MailHog, test only)       │
└────────┬──────────────┬──────────────────────────────────────────┘
         │              │
┌────────▼──────────────▼──────────┐
│  nginx                           │  SSL termination, HTTP→HTTPS
│  nginx:1.27-alpine               │  redirect, static file serving
└────────────────┬─────────────────┘
                 │  proxy_pass http://flask:5000
┌────────────────▼─────────────────┐
│  flask (Gunicorn + Flask 3.1)    │  Application logic
│  4 sync workers                  │
└──────┬──────────────┬────────────┘
       │              │
┌──────▼──────┐  ┌────▼───────────────────────────────────────┐
│  db          │  │  ldap (test stack only)                    │
│  PostgreSQL  │  │  osixia/openldap — stands in for AD in dev │
│  16          │  └────────────────────────────────────────────┘
└─────────────┘
```

**Production** uses an external LDAP/Active Directory server. The `ldap` container only exists in the test stack.

## Python application structure

```
app/
├── app.py                  Application factory (create_app)
├── factories/
│   └── log_factory.py      Shared RotatingFileHandler logger factory
├── helpers/
│   ├── csrf_helper.py      CSRF token generation and validation
│   ├── decorator_helper.py Route guard decorators
│   ├── rate_limiter.py     In-memory sliding-window rate limiter
│   └── utility_helper.py  Filename generation, image validation, password rules
├── routes/
│   ├── admin_routes.py     Admin portal routes (/admin, /admin_panel, …)
│   ├── user_routes.py      End-user routes (/, /login, /upload_photo, …)
│   └── auth_routes.py      OAuth 2.0 / Entra ID callback routes
├── services/
│   ├── auth_service.py     Authentication logic (local + Entra), session management, BFA
│   ├── admin_service.py    Admin CRUD and panel data population
│   ├── db_utils.py         psycopg2 connection pool wrapper
│   ├── email_service.py    All outbound email via Flask-Mail
│   ├── ldap_service.py     LDAP bind, user search, credential verification
│   └── submission_service.py  ID request lifecycle (create, approve, reject, delete, search)
├── templates/              Jinja2 HTML and email templates
├── static/                 CSS, JS, images
├── tests/                  pytest unit tests (see testing.md)
└── pytest.ini
```

## Request lifecycle

### End-user login (LDAP path)

```
POST /login
  → rate_limiter.is_allowed(remote_addr)     [blocks after 10 req / 5 min]
  → LDAPService.auth_user(email, password)
      → AuthService.check_bfa(email, ip, failed=False)   [blocks if locked]
      → LDAPService.check_user_submissions(email)         [blocks if pending/approved]
      → LDAPService.search_user(email)                    [service-account bind + search]
      → ldap.simple_bind_s(user_dn, password)             [credential verify]
  → AuthService.set_session_attrs(attrs)
  → redirect /landing
```

### Admin login (local path)

```
POST /admin
  → AuthService.admin_login(username, password)
      → AuthService.check_bfa(username, ip, failed=False)
      → SELECT admins WHERE username = %s
      → bcrypt.checkpw(password, stored_hash)
      → on failure: check_bfa(username, ip, failed=True)  [increment / insert BFA record]
      → on success: populate session
  → redirect /admin_panel  (or /change_admin_password if on_login=1)
```

### OAuth (Entra ID) path

```
GET /oauth/login?flow=admin|user
  → validate ENTRA_CLIENT_ID configured + auth mode allows it
  → store flow in session['oauth_flow']
  → authlib: redirect to Microsoft authorize endpoint

GET /oauth/callback
  → authlib: exchange code for token, fetch userinfo from id_token
  → flow == 'admin': AuthService.entra_admin_login(userinfo)
  → flow == 'user':  AuthService.entra_user_login(userinfo)
  → redirect to appropriate destination
```

## Service dependencies

Services are instantiated once in `create_app()` and attached to the `app` object. Routes access them via `current_app.<service>`.

```
Database
  └── used by: AuthService, AdminService, SubmissionService,
               EmailService, LDAPService

AuthService(db)
  └── used by: LDAPService, admin_routes, auth_routes

LDAPService(auth_service, app, db)
  └── used by: user_routes

EmailService(db, app)
  └── used by: admin_routes, user_routes

AdminService(db)
  └── used by: admin_routes

SubmissionService(db, email_service)
  └── used by: admin_routes, user_routes
```

## Session design

Flask's signed cookie session (`itsdangerous`) is used. No server-side session store.

**Admin session keys:**

| Key | Type | Description |
|---|---|---|
| `admin_username` | str | Username — presence signals admin is logged in |
| `first_name` | str | Display name |
| `last_name` | str | Display name |
| `email` | str | Admin email |
| `role` | str | `super` or `manager` |
| `on_login` | int | `1` = must change password before proceeding |
| `user_id` | int | `admins.id` |
| `forgot_password_token` | str | Set during password-reset flow; unlocks `/change_admin_password` |

**User session keys:**

| Key | Type | Description |
|---|---|---|
| `user_logged_in` | bool | True when authenticated |
| `attrs` | dict | Raw LDAP/Entra attributes dict |
| `First Name` | str | Pulled from attrs for template use |
| `Last Name` | str | |
| `Email` | str | |
| `ID Number` | str | employeeID from LDAP |
| `Location` | str | physicalDeliveryOfficeName from LDAP |
| `cn` | str | sAMAccountName / preferred_username |
| `request_id` | int | Set after successful submission insert |

Sessions are permanent with an 8-hour lifetime (`PERMANENT_SESSION_LIFETIME`). The cookie is `HttpOnly`, `SameSite=Lax`, and `Secure=True` (the last two enforced by nginx in production).

## Logging

Each service creates its own named logger via `factories.get_logger(name)`. All loggers write to `logs/<name>.log` using a `RotatingFileHandler` (1 MB max, 5 backups). The `logs/` directory is a Docker named volume so logs persist across container restarts. Log format:

```
[YYYY-MM-DD HH:MM:SS] {service_name}: LEVEL - message
```

Audit-relevant events (submission approve / reject / delete) are written with the prefix `[AUDIT]` to make them grep-able.
