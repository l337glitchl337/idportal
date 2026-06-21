# Testing

## Running tests

Tests run inside the Flask container. After a rebuild, pytest is available directly:

```bash
docker compose exec flask python -m pytest tests/ -v
```

Without a rebuild, install pytest in the running container first:

```bash
docker exec flask_test pip install pytest
docker exec flask_test python -m pytest tests/ -v
```

Run a single file:

```bash
docker compose exec flask python -m pytest tests/test_auth_service.py -v
```

Run a single test:

```bash
docker compose exec flask python -m pytest tests/test_auth_service.py::test_admin_login_success -v
```

## Configuration

`app/pytest.ini`:

```ini
[pytest]
testpaths = tests
pythonpath = .
```

`pythonpath = .` puts `/app` on `sys.path`, enabling top-level imports (`from services.auth_service import AuthService`, etc.) without package installs.

## Architecture

Tests live in `app/tests/`. No real database, LDAP connection, or SMTP server is used — all services are replaced with `unittest.mock.MagicMock` instances.

### `conftest.py`

Defines a `make_app()` factory that creates a minimal Flask app:

- Registers all three blueprints (`admin`, `user`, `auth`)
- Attaches mock services (`app.db`, `app.auth_service`, `app.admin_service`, `app.ldap_service`, `app.email_service`, `app.submission_service`)
- Sets required config values with safe test defaults
- Does **not** register the CSRF `before_request` hook (CSRF is tested independently in `test_csrf_helper.py`)
- Does **not** call `init_oauth` (OAuth is tested by patching `routes.auth_routes.oauth` directly)

Fixtures provided:

| Fixture | Description |
|---|---|
| `app` | Fresh Flask test app per test |
| `client` | Unauthenticated test client |
| `admin_client` | Test client with super admin session pre-set |
| `manager_client` | Test client with manager session pre-set |
| `user_client` | Test client with end-user session pre-set |

Route tests that need a specific auth mode (e.g. `ADMIN_AUTH_MODE=entra`) use `make_app(ADMIN_AUTH_MODE='entra')` directly.

### Mocking services in route tests

Service mock return values are set per test before calling the route:

```python
def test_approve_submission_success(app, admin_client):
    app.submission_service.approve_request.return_value = True
    resp = admin_client.post('/approve_submission', data={'request_id': '1'})
    assert resp.get_json()['success'] is True
```

For routes that render templates, `render_template` is patched at the module level to avoid template rendering errors:

```python
with patch('routes.admin_routes.render_template', return_value=''):
    resp = admin_client.get('/admin_panel?active_tab=pending')
```

### Mocking DB in service tests

Service tests instantiate the service directly with a `MagicMock` DB:

```python
db = MagicMock()
svc = AuthService(db=db)
```

`db.execute_query.return_value` sets a single return value; `db.execute_query.side_effect` sets a list consumed one call at a time. This is necessary when a method makes multiple DB calls in sequence (e.g. `admin_login` calls `check_bfa` which does its own `execute_query`, then the admins SELECT):

```python
db.execute_query.side_effect = [
    None,  # check_bfa: no existing BFA record
    ("First", "Last", "user", "u@e.com", hashed, 1, "super", 0, 42),  # admins SELECT
]
```

### Flask context in service tests

Methods that use `session`, `flash`, `request`, or `current_app` require an active request context:

```python
with app.test_request_context('/'):
    result = svc.update_admin_password("user", "NewPass1!")
```

Assertions against `session` must also be inside the context:

```python
with app.test_request_context('/'):
    svc.entra_admin_login(userinfo)
    assert session.get('admin_username') == 'admin'  # ← inside the with block
```

## Test file index

| File | Component | Tests |
|---|---|---|
| `test_utility_helper.py` | `UtilityHelper` | 19 |
| `test_rate_limiter.py` | `RateLimiter` | 7 |
| `test_csrf_helper.py` | `generate_csrf_token`, `validate_csrf` | 10 |
| `test_decorator_helper.py` | `DecoratorHelper` | 9 |
| `test_auth_service.py` | `AuthService` | 28 |
| `test_admin_service.py` | `AdminService` | 14 |
| `test_submission_service.py` | `SubmissionService` | 13 |
| `test_admin_routes.py` | `admin_routes` blueprint | 47 |
| `test_user_routes.py` | `user_routes` blueprint | 16 |
| `test_auth_routes.py` | `auth_routes` blueprint | 13 |
| **Total** | | **181** |

## Adding new tests

1. Add the test function to the appropriate file, or create a new file prefixed `test_`.
2. If testing a route that renders a template, patch `render_template` in the relevant module namespace (`routes.admin_routes.render_template`, etc.).
3. If testing a service method that makes multiple sequential DB calls, use `side_effect` with a list rather than `return_value`.
4. If the method under test accesses `session`, `flash`, or `request`, wrap the call in `app.test_request_context('/')`.
5. Rebuild the image (`docker compose build`) or copy the file into the running container (`docker cp`) before running.
