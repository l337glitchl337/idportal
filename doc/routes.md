# Routes

All routes are registered on the Flask `app` via blueprints in `create_app()`. CSRF validation runs as a `before_request` hook on every POST. The `ProxyFix` middleware is applied so `request.remote_addr` reflects the real client IP from the `X-Forwarded-For` header set by nginx.

---

## Auth modes

Two environment variables control which login paths are active:

| Variable | Values | Effect |
|---|---|---|
| `ADMIN_AUTH_MODE` | `local` (default) | Password form only; Microsoft button hidden; OAuth and password-reset routes blocked in Entra-only mode |
| | `entra` | Microsoft sign-in only; password form hidden; `POST /admin` and `/forgot_password` routes reject with flash |
| | `both` | Both methods shown |
| `USER_AUTH_MODE` | `ldap` (default) | LDAP form only |
| | `entra` | Microsoft sign-in only; `POST /login` rejects with flash |
| | `both` | Both methods shown |

These values are injected into every template via the `inject_globals` context processor as `admin_auth_mode` and `user_auth_mode`.

---

## Route guards (decorators)

Defined in `helpers/decorator_helper.py`. Applied as stacked decorators — Flask calls them outer-first, so `check_admin_login` runs before `check_first_login`.

### `@DecoratorHelper.check_login`
Checks `session['user_logged_in']` is truthy. Redirects to `/` on failure.

### `@DecoratorHelper.check_admin_login`
Special case: if `forgot_password_token` is in session, only the `admin.change_admin_password` endpoint is allowed through; any other endpoint redirects to `/admin`.

Otherwise: checks `session['admin_username']` is present. Redirects to `/admin` on failure.

### `@DecoratorHelper.check_first_login`
Checks `session['on_login'] != 1`. Redirects to `/admin` if the admin has not yet changed their initial password.

---

## User routes (`routes/user_routes.py`)

Blueprint: `user`, prefix: `/`

### `GET /`
Renders `login.html`. No auth required. The template conditionally shows the LDAP form and/or the Microsoft button based on `user_auth_mode` and `entra_enabled`.

### `POST /login`
LDAP authentication endpoint.

- Blocked (redirect `/`) if `USER_AUTH_MODE == "entra"`.
- Rate-limited by `login_limiter` (10 req / 5 min per IP).
- Delegates to `LDAPService.auth_user(email, password)`.
- On success: `AuthService.set_session_attrs(attrs)` → redirect `/landing`.
- On failure: flash error → redirect `/`.

### `GET /landing`
**Guard:** `check_login`  
Renders `landing.html` with `attrs=session['attrs']`. Shows the user their LDAP/Entra profile data and the link to the upload form.

### `GET /upload_form`
**Guard:** `check_login`  
Renders `upload_photo.html` — the photo and licence upload form.

### `POST /upload_photo`
**Guard:** `check_login`  
Handles file submission.

1. Validates both `photo` and `drivers_license` fields are present and non-empty.
2. Calls `UtilityHelper.is_valid_image()` on each file — rejects with flash if invalid.
3. Generates UUID filenames and saves to `UPLOAD_FOLDER`.
4. Calls `SubmissionService.create_submission(photo_fn, license_fn)`.
5. On success: sends admin email alert → redirect `/logout` (clears user session).
6. On DB failure: deletes the saved files, flashes error, redirect `/logout`.

Saving files before the DB insert means a DB failure requires cleanup (the `os.remove` calls in the failure branch). The reverse order (insert first, then save) would be cleaner but the current code handles it correctly.

---

## Admin routes (`routes/admin_routes.py`)

Blueprint: `admin`, prefix: `/`

Input validation constants at module level:
- `_VALID_ROLES = {'manager', 'super'}`
- `_MAX_COMMENT_LEN = 250`
- `_NAME_RE = r"^[A-Za-z\s'\-]{1,50}$"`
- `_USERNAME_RE = r"^[A-Za-z0-9_]{3,20}$"`
- `_EMAIL_RE = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"`

### `GET|POST /admin`
Admin login page.

- `GET`: renders `admin.html`.
- `POST`: blocked if `ADMIN_AUTH_MODE == "entra"`. Calls `AuthService.admin_login`. On success, redirects to `/change_admin_password` if `session['on_login'] == 1`, otherwise to `/admin_panel?active_tab=pending`.

### `GET /admin_panel`
**Guards:** `check_admin_login`, `check_first_login`

Main admin panel. Reads `page` and `active_tab` query params.

- If `search_term` query param present: calls `SubmissionService.search` → renders with `search_results`. No results → flash + redirect to search tab.
- Otherwise: calls `AdminService.populate_admin_panel(page, active_tab)` → renders `admin_panel.html`.

Passes `current_user` dict (`username`, `role`, `email`, `user_id`) to the template for self-edit guards.

### `POST /logout`
Clears session while preserving flash messages (copies `_flashes`, clears session, restores them). Redirects to `/admin` for admin sessions, `/` for user sessions.

### `POST /reject_submission`
**Guards:** `check_admin_login`, `check_first_login`  
**Returns:** JSON `{success, message}`

Validates `comments` length ≤ 250. Calls `SubmissionService.reject_request(request_id, comments, actor)`.

### `POST /approve_submission`
**Guards:** `check_admin_login`, `check_first_login`  
**Returns:** JSON `{success, message}`

Calls `SubmissionService.approve_request(request_id, actor)`.

### `POST /batch_edit`
**Guards:** `check_admin_login`, `check_first_login`  
**Returns:** JSON `{success, message[, errors]}`

Accepts `action` (`approve` or `reject`), `request_ids[]` (list), and optional `comments`. Iterates over IDs and calls the appropriate service method. Collects failures into `errors` dict; returns partial-failure response if any fail.

### `POST /create_admin_account`
**Guards:** `check_admin_login`, `check_first_login`  
**Role required:** `super`

In `local`/`both` mode: validates `first_name`, `last_name`, `username` (regex), `email`, `role`. Calls `AdminService.create_admin` then `EmailService.send_welcome_email`.

In `entra` mode: only `email` and `role` are required. `first_name` is set to `"Pending"`, `last_name` to `""`, `username` auto-derived from the email local-part (`re.sub(r'[^A-Za-z0-9_]', '', email.split('@')[0])[:20]`). Sends `EmailService.send_entra_welcome_email` instead.

### `POST /edit_admin_account`
**Guards:** `check_admin_login`, `check_first_login`  
**Role required:** `super`

Validates all fields. Blocks self-edit (`user_id_int == session['user_id']`) — admins must use the profile tab to edit their own account. Calls `AdminService.edit_admin`.

### `POST /delete_admin_account`
**Guards:** `check_admin_login`, `check_first_login`  
**Role required:** `super`  
**Returns:** JSON `{success, message}`

Blocks self-delete. Calls `AdminService.delete_admin`.

### `POST /search_submissions`
**Guards:** `check_admin_login`, `check_first_login`

Redirects to `GET /admin_panel?active_tab=search&search_term=<term>`. Exists to handle the search form as a POST (the actual search logic lives in `GET /admin_panel`).

### `POST /delete_submission`
**Guards:** `check_admin_login`, `check_first_login`  
**Returns:** JSON `{success, message, errors}`

Calls `SubmissionService.delete(request_id, actor)`.

### `GET|POST /change_admin_password`
**Guard:** `check_admin_login`

- Blocked if `ADMIN_AUTH_MODE == "entra"` AND `forgot_password_token` is not in session. (Entra admins cannot set local passwords except via a reset link.)
- `GET`: renders `change_admin_password.html`. Template shows different fields if `forgot_password_token` is in session (no current-password field).
- `POST` (normal): verifies current password via `AuthService.compare_password`, checks new/confirm match, calls `AuthService.update_admin_password`.
- `POST` (forgot-password flow): skips current-password check (token in session proves identity). Calls `AuthService.del_forgot_password_token` after success. Clears session and redirects to `/admin`.

### `GET|POST /forgot_password`
No auth required. Blocked if `ADMIN_AUTH_MODE == "entra"`.

- `GET` without token: renders `admin_forgot_password.html`.
- `GET` with `?token=<value>`: calls `AuthService.validate_forgot_password_token`. On success, sets `session['admin_username']` and `session['forgot_password_token']`, redirects to `/change_admin_password`. On failure, flashes and redirects to `/admin`.
- `POST`: rate-limited by `forgot_password_limiter` (5 req / 5 min per IP). Accepts `identifier` (email or username). Calls `EmailService.send_forgot_password_email`. Always flashes a neutral message regardless of whether the account exists.

### `GET /uploads/<path:filename>`
**Guard:** `check_admin_login`

Serves uploaded files from `UPLOAD_FOLDER` via `send_from_directory`. The `check_admin_login` guard ensures only authenticated admins can access submitted photos.

---

## OAuth routes (`routes/auth_routes.py`)

Blueprint: `auth`, prefix: `/`

The `oauth` object is a module-level `authlib.integrations.flask_client.OAuth` instance, initialised by `init_oauth(app)` in `create_app()`. The Entra client is registered with the Microsoft OpenID Connect discovery endpoint:

```
https://login.microsoftonline.com/{ENTRA_TENANT_ID}/v2.0/.well-known/openid-configuration
```

### `GET /oauth/login`

Query param `flow`: `admin` or `user` (defaults to `user`).

- If `ENTRA_CLIENT_ID` not configured: flash error, redirect to appropriate home.
- If `flow=admin` and `ADMIN_AUTH_MODE == "local"`: reject.
- If `flow=user` and `USER_AUTH_MODE == "ldap"`: reject.
- Otherwise: store `flow` in session, call `oauth.entra.authorize_redirect(callback_url)`.

### `GET /oauth/callback`

- Calls `oauth.entra.authorize_access_token()` — exchanges the auth code for an access token and fetches the ID token userinfo.
- Pops `session['oauth_flow']` (defaults to `'user'` if missing).
- `flow == 'admin'`: `AuthService.entra_admin_login(userinfo)` → redirect `/admin_panel` or `/admin`.
- `flow == 'user'`: `AuthService.entra_user_login(userinfo)` → redirect `/landing` or `/`.
- Any exception from the token exchange: flash error, redirect `/`.

---

## Error handlers

Registered in `create_app()`:

| Code | Template |
|---|---|
| 404 | `404.html` |
| 500 | `500.html` |

400 (CSRF abort) is handled by Werkzeug's default error response — there is no custom template for it.
