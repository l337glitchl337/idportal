# Database

PostgreSQL 16. Schema defined in `docker/db/init.sql`. The database user is `idportal` and has `SELECT`, `INSERT`, `UPDATE`, `DELETE` on all tables, plus `USAGE` on all sequences. It does not have DDL privileges — schema changes require a superuser connection.

---

## Tables

### `admins`

Stores admin portal accounts.

| Column | Type | Default | Description |
|---|---|---|---|
| `id` | `integer` | auto (sequence) | Primary key |
| `first_name` | `text` | — | Display name |
| `last_name` | `text` | — | Display name |
| `username` | `varchar(20)` | — | Login identifier; unique |
| `password` | `text` | — | bcrypt hash (cost 12) |
| `email` | `text` | — | Used for Entra login matching and password reset; unique |
| `status` | `integer` | `1` | `1` = active, `0` = disabled |
| `on_login` | `integer` | `1` | `1` = must change password on next login; reset to `0` after change |
| `role` | `varchar(8)` | — | `super` or `manager` |

**Constraints:** `admins_pkey` (PK on `id`), `admins_email_key` (UNIQUE on `email`), `admins_username_key` (UNIQUE on `username`).

**Indexes:** B-tree on `id`, `username`, `email` — all three are frequent lookup keys.

**Notes:**
- `on_login = 1` is set on every newly created account. The deploy script also sets it on the bootstrap super admin. This forces a password change via the `/change_admin_password` route before the admin can access anything else.
- `password` stores the full bcrypt output string (60 chars), which embeds the algorithm version, cost factor, and salt. The plain-text password is never stored or logged.
- In Entra-only mode (`ADMIN_AUTH_MODE=entra`) the `password` column contains a randomly generated bcrypt hash that is never used; `username` is auto-derived from the email prefix.

---

### `admin_forgot_password`

Holds single-use password-reset tokens.

| Column | Type | Default | Description |
|---|---|---|---|
| `id` | `integer` | auto | Primary key |
| `user_id` | `integer` | — | FK → `admins.id` |
| `token` | `varchar(64)` | — | SHA-256 hex digest of the raw token |
| `expire_after` | `timestamptz` | `now() + 30 min` | Token expiry; overridden to `+24 hours` on account creation emails |

**Constraints:** `admin_forgot_password_pkey` (PK on `id`), FK on `user_id` referencing `admins(id)`.

**Notes:**
- The raw token (UUID4 hex, 32 chars) is sent in the reset URL. Only the SHA-256 hash of that token is stored. This means a database breach does not expose usable reset links.
- On forgot-password form submit, a dummy `gen_random_forgot_password_link()` call is made even when the account does not exist. This normalises response time and prevents username/email enumeration.
- Tokens are deleted from this table immediately after a successful password reset (`del_forgot_password_token`).
- Multiple tokens can exist for the same `user_id`. The query validates by token hash only; if a user requests multiple resets, all are usable until expiry. Tokens are short-lived (30 min for forgot-password flow, 24 hours for welcome emails), so this is acceptable.

---

### `submissions`

One row per ID request submitted by an end user.

| Column | Type | Default | Description |
|---|---|---|---|
| `request_id` | `integer` | auto | Primary key |
| `first_name` | `text` | — | From LDAP/Entra at time of submission |
| `last_name` | `text` | — | |
| `email` | `text` | — | |
| `id_number` | `text` | — | Employee/student ID (employeeID from LDAP) |
| `location` | `varchar(15)` | — | Campus/office (physicalDeliveryOfficeName from LDAP) |
| `timestamp_inserted` | `timestamptz` | `now()` | Submission time |
| `status` | `varchar(1)` | `'N'` | `N` = pending, `A` = approved, `R` = rejected |
| `ip_address` | `inet` | — | Populated by DB default (currently unused at app level — see note) |
| `photo_filepath` | `text` | — | UUID-based filename in the `uploads` volume |
| `license_filepath` | `text` | — | UUID-based filename in the `uploads` volume |
| `comments` | `varchar(250)` | — | Rejection reason; null for pending/approved |
| `search_vector` | `tsvector` | generated | Full-text search index (see below) |

**Constraints:** `submissions_pkey` (PK on `request_id`).

**Indexes:**
- B-tree on `status` — all panel queries filter by status.
- B-tree on `email` — duplicate-submission check.
- B-tree on `id_number` — search support.
- GIN on `search_vector` — full-text search.

**`search_vector` generated column:**

```sql
to_tsvector('english',
    COALESCE(first_name,'') || ' ' ||
    COALESCE(last_name,'') || ' ' ||
    COALESCE(id_number,'') || ' ' ||
    COALESCE(email,'') || ' ' ||
    COALESCE(location::text,'') || ' ' ||
    COALESCE(comments::text,'')
)
```

This is a `GENERATED ALWAYS AS ... STORED` column. PostgreSQL recomputes and stores it automatically on every insert/update. The `english` dictionary applies stemming and stop-word removal. Searches use `plainto_tsquery('english', ?)` which tokenises the search term the same way. GIN indexing on `tsvector` gives O(log n) lookup rather than a sequential scan.

**Note on `ip_address`:** The column exists in the schema but the application layer does not pass a value on insert (the `INSERT` statement in `submission_service.py` does not include it). PostgreSQL accepts the omission and stores `NULL`.

---

### `bfa`

Brute-force protection tracking table for admin login attempts. See also [algorithms.md — Brute-force lockout](algorithms.md#brute-force-lockout-bfa).

| Column | Type | Default | Description |
|---|---|---|---|
| `id` | `integer` | auto | Primary key |
| `email` | `text` | — | The username/email that was targeted |
| `ip_address` | `inet` | — | Source IP of the first failed attempt |
| `failed_attempts` | `integer` | `1` | Incremented on each subsequent failure |
| `timestamp_inserted` | `timestamp` (no tz) | `now()` | Reset to `now()` on each increment |

**Constraints:** `bfa_pkey` (PK on `id`), `bfa_email_key` (UNIQUE on `email`).

**Indexes:** B-tree on `email` — every auth attempt does a lookup by email.

**Notes:**
- One row per targeted username. Multiple IPs attacking the same account will still lock it out after 3 total failures.
- `timestamp_inserted` is refreshed (`= now()`) on every failed-attempt increment, meaning the 30-minute window is a sliding window from the *last* failure, not the first.
- Rows are deleted when the lockout window expires (not on successful login). A successful login after the window naturally re-creates a clean row if needed.

---

## Entity relationship

```
admins (1) ──────────────── (0..*) admin_forgot_password
       id                          user_id (FK)

submissions — no FK relationships; email is the only join key
              (intentional: submissions must survive admin account deletion)

bfa — no FK relationships; email is a free-text key matching the login
      identifier, which may be a username rather than a real email
```

---

## Connection pooling

`db_utils.py` wraps a `psycopg2.pool.ThreadedConnectionPool` with `minconn=2`, `maxconn=10`. Connections are checked out for the duration of a single query and immediately returned to the pool. All writes commit on success and roll back on exception. The pool is shared across Gunicorn's sync workers via the Flask `app` object — because Gunicorn prefork workers do not share memory, each worker has its own pool instance.
