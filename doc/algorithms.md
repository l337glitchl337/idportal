# Algorithms and Security Mechanisms

---

## Brute-force lockout (BFA)

**Location:** `services/auth_service.py` — `AuthService.check_bfa`  
**Triggers on:** Admin local login (`POST /admin`) and LDAP user login (`POST /login`)

### How it works

The `bfa` table holds one row per targeted account identifier (username or email). The algorithm runs as a guard both *before* and *after* a credential check.

**Before the credential check** (`failed=False`):

```
SELECT * FROM bfa WHERE email = ?
├── No row found
│     └── allow login attempt (return True)
└── Row found
      ├── failed_attempts < 3
      │     └── allow login attempt (return True)
      └── failed_attempts >= 3
            ├── (now - timestamp_inserted) > 30 min  → delete row, return True
            └── (now - timestamp_inserted) <= 30 min → log lockout time, return False
```

**After a failed credential check** (`failed=True`):

```
SELECT * FROM bfa WHERE email = ?
├── No row found
│     └── INSERT bfa (email, ip_address)  [failed_attempts defaults to 1]
└── Row found, failed_attempts < 3
      └── UPDATE bfa SET failed_attempts = failed_attempts + 1,
                         timestamp_inserted = now()
```

Note: when `failed_attempts >= 3` and `failed=True` (i.e. repeated attempts while locked), the update branch is not reached because `check_bfa` returns `False` before the credential check even runs, so the second `check_bfa(failed=True)` call never happens.

### Key design decisions

- **Sliding window from last failure:** `timestamp_inserted` is updated to `now()` on every failed-attempt increment. The 30-minute window restarts from the most recent failure, not the first. This prevents a slow drip attack (one attempt every 29 minutes) from evading the lockout.
- **Account-level, not IP-level:** The lockout key is the targeted username/email, not the source IP. Multiple IPs attacking the same account cooperatively consume the failure budget. A single IP attacking multiple accounts is not blocked by this mechanism — rate limiting handles that (see below).
- **No automatic reset on successful login:** Rows are only deleted when the 30-minute window expires. A successful login after the window expires will find no row and proceed normally.

---

## Rate limiting

**Location:** `helpers/rate_limiter.py` — `RateLimiter`  
**Instances:** `forgot_password_limiter` (5 req / 5 min), `login_limiter` (10 req / 5 min)

### Algorithm: sliding window counter

```python
def is_allowed(self, key: str) -> bool:
    now = time.time()
    with self._lock:
        calls = self._calls[key]
        calls[:] = [t for t in calls if now - t < self.period]  # evict expired timestamps
        if len(calls) >= self.max_calls:
            return False
        calls.append(now)
        return True
```

Each `key` (typically a remote IP) maps to a list of timestamps. On every call:
1. Timestamps older than `period` seconds are removed in place.
2. If the remaining count meets or exceeds `max_calls`, the request is denied.
3. Otherwise the current timestamp is appended and the request is allowed.

This is a true sliding window (not a fixed bucket). A client that makes 5 requests in the last second of a window cannot "reload" on the first second of the next window.

### Trade-offs

- **In-memory only:** The store is a `defaultdict(list)` on the process. In a multi-worker Gunicorn setup, each worker has an independent counter. A client can make `max_calls × worker_count` requests before any single worker rejects them. With 4 workers and `login_limiter(10, 300)`, that is effectively 40 attempts per 5 minutes per IP per deployment. This is acceptable given BFA and bcrypt cost also slow attacks.
- **No persistence:** Counters reset on container restart.
- **Thread safety:** A `threading.Lock` protects the shared dict. This is correct for Gunicorn's sync (pre-fork, threaded) workers.

---

## CSRF protection

**Location:** `helpers/csrf_helper.py`  
**Applied:** `app.before_request(validate_csrf)` — runs on every request before any route handler.

### Double-submit cookie pattern

```python
def generate_csrf_token() -> str:
    if 'csrf_token' not in session:
        session['csrf_token'] = secrets.token_hex(32)
    return session['csrf_token']

def validate_csrf() -> None:
    if request.method != 'POST':
        return
    token = session.get('csrf_token')
    form_token = request.form.get('csrf_token') or request.headers.get('X-CSRF-Token')
    if not token or not form_token or not hmac.compare_digest(token, form_token):
        abort(400)
```

On the first GET to any page, `generate_csrf_token()` (called from the context processor) stores a 64-character hex token in the session cookie. Every HTML form includes a hidden `<input name="csrf_token">` with this value. On POST, `validate_csrf` compares the session token against the submitted value using `hmac.compare_digest` (constant-time comparison, preventing timing attacks).

AJAX endpoints can also pass the token in the `X-CSRF-Token` header — the check accepts either.

GET, HEAD, and other safe methods are exempt.

---

## Password hashing

**Location:** `services/auth_service.py`

bcrypt with an auto-generated salt (cost factor determined by `bcrypt.gensalt()`, currently 12 rounds).

```python
salt = bcrypt.gensalt()
hashed = bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')
```

The stored string is the full bcrypt output: `$2b$12$<22-char salt><31-char hash>` (60 chars). Verification uses `bcrypt.checkpw` which re-derives the hash using the embedded salt and compares in constant time.

**Password complexity rules** (`helpers/utility_helper.py`):
- Minimum 8 characters, maximum 128 characters
- Must contain: at least one lowercase letter, one uppercase letter, one digit, one non-alphanumeric character (`[\W_]` — underscore counts)
- Enforced by regex: `^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[\W_]).{8,}$`
- The maximum of 128 is a DoS guard: bcrypt has O(n) cost per character; extremely long passwords can be used to exhaust CPU.

---

## Password reset token

**Location:** `services/auth_service.py` — `gen_random_forgot_password_link`, `_hash_token`

```python
token = uuid4().hex          # 32-char random hex string
url   = f"{FORGOT_PASSWORD_URL}?token={token}"
stored = sha256(token.encode()).hexdigest()   # 64-char hex
```

The raw token is embedded in the URL sent to the user. Only the SHA-256 hash is stored in the database. If the `admin_forgot_password` table is dumped, the hashes cannot be used directly — an attacker would need to find a UUID4 that hashes to a known value, which is computationally infeasible.

UUID4 provides 122 bits of entropy (4 bits are version/variant markers). Token expiry is enforced at the database level via `expire_after`.

---

## Image validation

**Location:** `helpers/utility_helper.py` — `is_valid_image`

Two-stage validation:

1. **Extension check:** The filename (after `werkzeug.utils.secure_filename` normalisation) must have an extension in `{.jpg, .jpeg, .png, .webp}`.
2. **Magic bytes check:** The first 12 bytes of the file stream are read and compared against known signatures:
   - JPEG: `\xff\xd8\xff`
   - PNG: `\x89PNG\r\n\x1a\n`
   - WebP: `RIFF....WEBP` (bytes 0–3 are `RIFF`, bytes 8–11 are `WEBP`)

The stream seek position is reset to 0 after reading. The extension and magic bytes are checked independently — a valid magic signature in any accepted format is sufficient regardless of whether it matches the file extension. This intentionally accepts, for example, a JPEG renamed to `.png`.

The combination of extension + magic byte checks blocks common attack vectors: an attacker cannot upload a PHP/shell script by renaming it `.jpg` (the magic bytes won't match), and cannot bypass the extension check by using a valid JPEG header inside a `.php` file (the extension check fails first).

---

## File storage

**Location:** `helpers/utility_helper.py` — `generate_unique_filename`

```python
def generate_unique_filename(filename: str) -> str:
    filename = secure_filename(filename)          # strip path traversal, sanitise
    _, extension = os.path.splitext(filename)
    return f"{uuid4()}{extension}"               # e.g. "3f2a...c1.jpg"
```

Original filenames are discarded. The stored name is `UUID4 + original extension`. UUID4 provides a namespace large enough that collisions are negligible (2^122 values). The extension is kept only for MIME type hints in the future — the actual content type is validated by magic bytes before this function is called.

Files are stored in the `uploads` Docker named volume at `/app/uploads/` inside the container. They are served via the authenticated route `GET /uploads/<path:filename>` which is guarded by `@DecoratorHelper.check_admin_login`.

---

## Full-text search

**Location:** `services/submission_service.py` — `search`  
**Database:** `search_vector` generated column on `submissions`

PostgreSQL's built-in `tsvector`/`tsquery` engine is used.

The `search_vector` column is defined as:

```sql
GENERATED ALWAYS AS (
    to_tsvector('english',
        COALESCE(first_name,'') || ' ' || COALESCE(last_name,'') || ' ' ||
        COALESCE(id_number,'') || ' ' || COALESCE(email,'') || ' ' ||
        COALESCE(location::text,'') || ' ' || COALESCE(comments::text,'')
    )
) STORED
```

Search query:

```sql
SELECT * FROM submissions
WHERE search_vector @@ plainto_tsquery('english', ?)
ORDER BY request_id
LIMIT ? OFFSET ?
```

`plainto_tsquery` converts a free-text search string into a `tsquery` with implicit `AND` between all non-stop words. The `@@` operator checks whether the `tsvector` matches. The GIN index on `search_vector` enables this without a sequential scan.

The `english` text search configuration applies the Snowball stemming algorithm (e.g. "approved" and "approve" both match) and strips common English stop words.

---

## LDAP authentication flow

**Location:** `services/ldap_service.py`

Two-step bind pattern:

1. **Service account bind:** Connect to the LDAP server using the configured service account (`LDAP_BIND_DN` / `LDAP_BIND_PWD`) and search for the user entry matching the submitted email via `LDAP_SEARCH_FILTER`.
2. **User bind:** Disconnect the service connection, re-connect, and bind using the user's distinguished name (DN) returned from the search and the password the user submitted. If this bind succeeds, the credentials are valid.

This pattern is necessary because LDAP does not have a "verify password" primitive — the only way to check a password is to attempt a bind as that user.

TLS is applied via `StartTLS` (LDAP over port 389 upgraded to TLS) when `LDAP_USE_TLS=true`. The `LDAP_TLS_CACERTFILE` path is set as the CA trust store for certificate validation.

`LDAP_ATTRIBUTES` is a JSON mapping of display name → LDAP attribute name, e.g.:
```json
{"First Name": "givenName", "Last Name": "sn", "ID Number": "employeeID"}
```
This makes the attribute mapping configurable without code changes for different directory schemas.

**Duplicate-submission guard:** Before attempting authentication, `check_user_submissions` queries whether the submitting email already has a pending (`N`) or approved (`A`) submission. If so, the login is blocked with a message directing the user to contact their administrator. This prevents double-submissions without requiring the user to have a separate account state.
