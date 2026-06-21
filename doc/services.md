# Services

All services are instantiated in `create_app()` and attached to the Flask `app` object. Routes access them via `current_app.<service_name>`. Services do not import from routes — the dependency graph is strictly one-way.

---

## Database (`db_utils.py`)

```python
app.db = Database(app)
```

Thin wrapper around a `psycopg2.ThreadedConnectionPool`.

### `execute_query(query, params=(), fetch_one=False, fetch_all=False, dict_cursor=False)`

Executes a parameterised SQL statement.

| Parameter | Description |
|---|---|
| `query` | SQL string with `%s` placeholders |
| `params` | Tuple of values to bind |
| `fetch_one` | Return a single row tuple (or `None`) |
| `fetch_all` | Return a list of row tuples (or `RealDictRow` if `dict_cursor=True`) |
| `dict_cursor` | Use `psycopg2.extras.RealDictCursor`; rows accessible by column name |

**Return values:**
- `fetch_one=True` → single row tuple / `None`
- `fetch_all=True` → list of rows / empty list
- Neither → `True` on success, `None` on exception

Commits on success, rolls back on any exception, always returns the connection to the pool in the `finally` block.

---

## AuthService (`auth_service.py`)

```python
app.auth_service = AuthService(app.db)
```

Handles all credential checking, session population, and password management.

### `admin_login(username, password) → bool`

Authenticates an admin with local credentials. Checks BFA lockout before querying the DB, increments the failure counter on wrong password. Populates session on success.

Requires an active request context (`session`, `request.remote_addr`).

### `entra_admin_login(userinfo: dict) → bool`

Authenticates an admin via Entra ID. Looks up the admin by email (case-insensitive), checks `status`, updates `first_name`/`last_name` from the token if provided, then populates session. Does NOT use BFA — Microsoft handles brute-force on the OAuth side.

Requires an active request context.

### `entra_user_login(userinfo: dict) → bool`

Sets session attrs for an end user authenticated via Entra. Extracts `given_name`, `family_name`, `email`, and `preferred_username` from the ID token. Calls `set_session_attrs`.

### `set_session_attrs(attrs: dict) → bool`

Clears the current session, sets `session.permanent = True`, writes every key/value from `attrs`, and sets `session['user_logged_in'] = True` and `session['attrs'] = attrs`. Returns `True` on success, `False` on exception.

### `update_admin_password(username, new_password) → bool`

Validates password complexity, checks the new password is not the same as the current one, then updates the `admins` table with a new bcrypt hash and resets `on_login` to `0`.

Requires an active request context (uses `flash`).

### `compare_password(username, current_password) → bool`

Fetches the stored bcrypt hash for `username` and checks it against `current_password`. Used by the change-password form to verify the current password before allowing a change.

### `check_bfa(email, ip_address, failed) → bool`

Core brute-force protection. See [algorithms.md — Brute-force lockout](algorithms.md#brute-force-lockout-bfa) for full algorithm description.

- `failed=False`: pre-check (called before credential verification)
- `failed=True`: post-failure increment (called after a failed credential check)

### `gen_random_forgot_password_link() → (url, token)`

Generates a UUID4 hex token, constructs the reset URL from `FORGOT_PASSWORD_URL` config, returns both. The caller is responsible for storing `_hash_token(token)` in `admin_forgot_password`.

### `validate_forgot_password_token(token) → str | False`

Hashes `token` and queries `admin_forgot_password` joined with `admins` for a non-expired row. Returns the `username` on match, `False` otherwise.

### `del_forgot_password_token(token) → bool`

Deletes the row from `admin_forgot_password` matching the hash of `token`. Called after a successful password reset.

### `_hash_token(token) → str`

Returns `sha256(token.encode()).hexdigest()`. Internal utility used by token storage and lookup.

---

## AdminService (`admin_service.py`)

```python
app.admin_service = AdminService(app.db)
```

### `create_admin(first_name, last_name, username, email, role) → bool | None`

Inserts a new row into `admins`. Generates a random 32-byte URL-safe password, hashes it with bcrypt, and stores the hash. The admin cannot log in with local credentials until they go through the welcome-email password-set flow. Returns `True` on success, `None` on DB failure (falsy in either case — callers check `if result`).

### `edit_admin(user_id, first_name, last_name, username, email, role) → bool`

`UPDATE admins SET ... WHERE id = ?`. Returns `True` / `False`.

### `delete_admin(user_id) → bool`

`DELETE FROM admins WHERE id = ?`. Returns `True` / `False`. Self-deletion is prevented at the route layer, not here.

### `populate_admin_panel(page=1, per_page=15, active_tab=None) → dict`

Returns a data dict keyed to match template variables. Uses Python 3.10 `match/case` on `active_tab`.

| `active_tab` | Returns |
|---|---|
| `"pending"` | `pending_requests`, `pending_pagination` |
| `"approved"` | `approved_requests`, `approved_pagination` |
| `"rejected"` | `rejected_requests`, `rejected_pagination` |
| `"admins"` | `admins`, `admin_pagination` (super only; `{}` for managers) |
| anything else | `{"none": None}` |

Pagination dicts have keys: `total_pages`, `next_page` (None on last page), `prev_page` (None on first page). Rows fetched with `dict_cursor=True` so templates can access columns by name.

Requires an active request context (`session["role"]` is read for the admins tab).

---

## SubmissionService (`submission_service.py`)

```python
app.submission_service = SubmissionService(app.db, app.email_service)
```

### `create_submission(photo_filepath, license_filepath) → bool`

Reads the current user session for `First Name`, `Last Name`, `ID Number`, `Location`, `Email`. Inserts into `submissions` and stores the returned `request_id` in `session["request_id"]`. Requires an active request context.

### `approve_request(request_id, actor=None) → bool`

Sets `status = 'A'` for the given `request_id`, logs an audit entry, then calls `email_service.send_approved_email`. If the DB update fails, returns `False` without sending email.

### `reject_request(request_id, comments, actor=None) → bool`

Sets `status = 'R'` and `comments = ?` for the given `request_id`, logs an audit entry with the comments, then calls `email_service.send_rejection_email`. Same early-return pattern on DB failure.

### `search(search_term, page=1, per_page=15) → dict | None`

Runs a count query first; returns `None` immediately if count is 0. Otherwise runs the paginated `search_vector @@ plainto_tsquery(?)` query and returns `search_results` + `search_pagination`.

### `delete(request_id, actor=None) → bool`

`DELETE FROM submissions WHERE request_id = ?`. Logs audit entry. Does not delete associated files from the upload volume — those are orphaned. (Future work: clean up on delete.)

---

## LDAPService (`ldap_service.py`)

```python
app.ldap_service = LDAPService(app.auth_service, app, app.db)
```

### `search_user(email) → (dn, attrs)`

Binds as the service account, searches for `email` using `LDAP_SEARCH_FILTER` (e.g. `(mail={email})`), returns the DN and a `{display_name: value}` dict built from `LDAP_ATTRIBUTES`. Returns `(None, {})` on failure.

`ldap.filter.filter_format` is used to safely interpolate `email` into the filter string, preventing LDAP injection.

### `auth_user(email, password) → (message, attrs, success)`

Full authentication flow:
1. BFA pre-check
2. Duplicate-submission check
3. `search_user` to get DN
4. User bind to verify password
5. BFA failure increment on bind error

Returns a 3-tuple: an optional user-facing message string (or `None`), the attrs dict (or `None`), and a bool success flag.

### `check_user_submissions(email) → bool`

Queries the count of `submissions` with `status IN ('N', 'A')` for the given email. Returns `False` if ≥ 1 exists (blocking the login), `True` otherwise.

### `_start_tls(conn)`

Applies TLS options to an open LDAP connection and calls `start_tls_s()`. Sets `OPT_X_TLS_REQUIRE_CERT = DEMAND` (certificate verification is mandatory), optionally sets a custom CA cert file, and resets the TLS context (`OPT_X_TLS_NEWCTX = 0`).

---

## EmailService (`email_service.py`)

```python
app.email_service = EmailService(app.db, app)
```

Uses Flask-Mail. All send methods open a connection with `self.mail.connect()` (a persistent SMTP connection for the duration of the `with` block) and send via that connection. Exceptions are caught and logged; the return value indicates success.

### `send_email_alert() → bool`

Sends two emails on new submission: one to `MAIL_DEFAULT_RECIP` (the admin notification) and one to the submitting user confirming receipt. Reads submission details from the current session. Templates: `email/admin_email.html`, `email/student_email.html`.

### `send_welcome_email(username, first_name, email) → bool`

Sent when a new admin account is created (local auth mode). Generates a password-setup link (24-hour expiry), inserts the hashed token into `admin_forgot_password`, and emails the link. Template: `email/admin_welcome.html`.

### `send_entra_welcome_email(first_name, email) → bool`

Sent when a new admin account is created in Entra mode. No password link is generated — the email just instructs them to sign in with Microsoft. Template: `email/admin_welcome_entra.html`.

### `send_forgot_password_email(**kwargs) → bool`

Accepts either `email=` or `username=` as a keyword argument. Always calls `gen_random_forgot_password_link()` once as a dummy (to normalise timing), then — if the account exists — generates a real token, inserts it, and sends the email. Template: `email/forgot_password.html`.

### `send_approved_email(request_id) → bool`

Looks up `first_name || last_name` and `email` from `submissions` and sends an approval notification. Template: `email/approved_submission.html`.

### `send_rejection_email(request_id, comments) → bool`

Same lookup as above; includes rejection comments in the email. Template: `email/reject_submission.html`.
