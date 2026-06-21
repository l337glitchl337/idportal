# IDPortal — Technical Documentation

## Contents

| Document | What it covers |
|---|---|
| [architecture.md](architecture.md) | Container layout, Python module structure, request lifecycles, session design, logging |
| [database.md](database.md) | Full schema: all tables, columns, types, constraints, indexes, foreign keys, design notes |
| [algorithms.md](algorithms.md) | BFA lockout, sliding-window rate limiter, CSRF, bcrypt password hashing, reset tokens, image magic-byte validation, full-text search, LDAP two-step bind |
| [services.md](services.md) | Every service class and method — signatures, behaviour, dependencies |
| [routes.md](routes.md) | Every HTTP route — method, path, auth guards, request parameters, response format |
| [testing.md](testing.md) | How to run tests, test architecture, mocking patterns, adding new tests |

## Quick orientation

- Entry point: `app/app.py` — `create_app()` wires everything together.
- All services are on `current_app.<name>`; routes never instantiate services themselves.
- Schema migrations are manual — edit `docker/db/init.sql` and rebuild the `db` image.
- Auth mode (local vs Entra vs both) is controlled entirely by `ADMIN_AUTH_MODE` and `USER_AUTH_MODE` env vars; no code changes needed to switch modes.
