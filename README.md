# IDPortal

IDPortal is a web-based platform for submitting photo ID requests in organizational settings such as schools or workplaces. Users authenticate with their organization's credentials and submit ID requests without visiting a physical office. Administrators review, approve, or reject submissions through a secure admin panel.

## Tech Stack

- **Backend:** Python 3.12 / Flask 3.1 / Gunicorn
- **Database:** PostgreSQL 16
- **Authentication:** LDAP / Active Directory, Microsoft Entra ID (OAuth, optional)
- **Web Server:** Nginx 1.27 (SSL termination)
- **Containerization:** Docker / Docker Compose

## Requirements

- Docker with Docker Compose v2
- Git
- `openssl` (for certificate generation)

Rootless Docker is supported.

---

## Test Environment

The test stack runs the full application locally with OpenLDAP, MailHog (email capture), and a self-signed TLS certificate. No configuration is required.

```bash
git clone https://github.com/l337glitchl337/idportal.git
cd idportal
./deploy.sh --test
```

The script will:

1. Generate a `.env` with randomised secrets
2. Issue a self-signed TLS certificate
3. Build and start all containers (Flask, PostgreSQL, Nginx, OpenLDAP, MailHog)
4. Create a default super admin account (`testadmin`) and print a one-time password reset link

**Access:**

| Service | URL |
|---------|-----|
| Portal (user login) | `https://localhost:8443` |
| Admin panel | `https://localhost:8443/admin` |
| MailHog (captured emails) | `http://localhost:8025` |
| HTTP redirect | `http://localhost:8080` → `https://localhost:8443` |

Your browser will show a self-signed certificate warning — this is expected. Proceed past it.

**Test LDAP login:** `testuser@dev.local` / `TestPass123!`

### Changing default ports

Edit `.env` before deploying if the default ports conflict with something on your machine:

```env
HTTPS_PORT=8443
HTTP_PORT=8080
MAILHOG_PORT=8025
```

URL variables in `.env` update automatically on the next deploy.

### Updating the test stack

```bash
git pull
./deploy.sh --update
```

This backs up the database, rebuilds images with the latest code, and restarts containers.

### Stopping the test stack

```bash
docker compose -f docker-compose.test.yml down
```

To also wipe all data (volumes):

```bash
docker compose -f docker-compose.test.yml down -v
```

---

## Production Deployment

### First-time setup

```bash
git clone https://github.com/l337glitchl337/idportal.git
cd idportal
./deploy.sh
```

On first run the script generates a `.env` template and exits. Open it and replace every `CHANGE_ME` value, then run `./deploy.sh` again to continue.

### Required environment variables

**Flask**
```env
SECRET_KEY=<64+ character random string>
```

**Database**
```env
POSTGRES_DB=idportal
POSTGRES_USER=idportal
POSTGRES_PASSWORD=<strong password>
POSTGRES_HOST=db
POSTGRES_PORT=5432
```

**LDAP / Active Directory**
```env
LDAP_URI=ldap://your-dc.domain.com
LDAP_BIND_DN=CN=svc-idportal,OU=Service Accounts,DC=domain,DC=com
LDAP_BIND_PWD=<service account password>
LDAP_SEARCH_BASE=DC=domain,DC=com
LDAP_SEARCH_FILTER=(mail={email})
LDAP_USE_TLS=true
LDAP_TLS_CACERTFILE=/etc/ssl/certs/ca-certificates.crt
LDAP_ATTRIBUTES={"First Name":"givenName","Last Name":"sn","ID Number":"employeeID","Location":"physicalDeliveryOfficeName","cn":"cn","Email":"mail"}
```

**Email (SMTP)**
```env
MAIL_SERVER=smtp.domain.com
MAIL_PORT=587
MAIL_USE_TLS=true
MAIL_USERNAME=idportal@domain.com
MAIL_PASSWORD=<password>
MAIL_FROM_NAME=IDPortal
MAIL_FROM_ADDRESS=idportal@domain.com
MAIL_DEFAULT_RECIP=it@domain.com
```

**URLs and branding**
```env
SITE_TITLE=IDPortal
USER_LOGIN_URL=https://portal.domain.com/login
FORGOT_PASSWORD_URL=https://portal.domain.com/forgot_password
REVIEW_REQUEST_URL=https://portal.domain.com/admin_panel
ADMIN_URL=https://portal.domain.com/admin
COMPANY_NAME=Your Company
COMPANY_ADDRESS=123 Main St
COMPANY_STATE_ZIP=City, ST 00000
COMPANY_PHONE=(555) 555-5555
COMPANY_EMAIL_SIGNATURE=Your Company IT Department
```

### SSL certificates

Place your certificate files before deploying:

```
docker/nginx/certs/cert.pem
docker/nginx/certs/key.pem
```

The deploy script checks the certificate on every run and will not start if it is missing or expired within 30 days.

### First admin account

On first deploy the script detects no admin accounts and prompts you to create the initial super admin. A one-time password reset link is printed — open it in a browser to set the password. Subsequent deploys skip this step.

### Updating production

```bash
./deploy.sh --update
```

The script will:

1. Check whether your local branch is behind origin and offer to `git pull`
2. Take a compressed database backup to `backups/` before touching anything
3. Rebuild Docker images with the latest code and packages
4. Restart containers

Backups are retained automatically — the 10 most recent are kept and older ones are removed.

If the backup fails the script will warn you and ask for confirmation before continuing. Do not skip this unless you have a separate backup strategy in place.

### Starting completely fresh (wipe all data)

```bash
docker compose down -v
rm .env
./deploy.sh
```

---

## Admin Roles

There are two admin roles:

### Super Admin

Full access to everything:

- View, approve, reject, and delete ID submissions
- Search submissions
- Create, edit, and delete admin accounts
- Assign and change admin roles

The first account created by the deploy script is always a super admin. There must always be at least one super admin — you cannot delete your own account.

### Manager

Operational access without user management:

- View, approve, reject, and delete ID submissions
- Search submissions

Managers do not see the **Manage Admins** tab and cannot create or modify other admin accounts. Use this role for staff who process ID requests but should not have control over the admin portal itself.

---

## Authentication Modes

Two environment variables control which login methods are accepted:

```env
ADMIN_AUTH_MODE=local   # local | entra | both
USER_AUTH_MODE=ldap     # ldap  | entra | both
```

| Mode | Behaviour |
|------|-----------|
| `local` / `ldap` | Password or LDAP login only. Microsoft button hidden. (default) |
| `entra` | Microsoft sign-in only. Password/LDAP form hidden, routes blocked. |
| `both` | Both methods available. |

### Microsoft Entra ID (OAuth)

To enable "Sign in with Microsoft":

1. Azure Portal → Entra ID → App registrations → New registration
2. Supported account types: **Single tenant**
3. Add a redirect URI (Web): `https://yourdomain/oauth/callback`
4. Copy **Application (client) ID** and **Directory (tenant) ID**
5. Certificates & secrets → New client secret → copy the value
6. Set in `.env`:

```env
ENTRA_CLIENT_ID=<application id>
ENTRA_CLIENT_SECRET=<client secret>
ENTRA_TENANT_ID=<directory id>
ADMIN_AUTH_MODE=entra   # or both
USER_AUTH_MODE=entra    # or both
```

### Admin provisioning with Entra

Admin accounts must be created in the admin panel before an Entra login is accepted. A user whose Microsoft account email has no matching row in the `admins` table will be blocked with an error message.

When `ADMIN_AUTH_MODE=entra`, the create admin form only asks for **email** and **role** — no name or username is needed. The admin's name is populated automatically from their Entra profile on first login.

---

## Data Locations

All persistent data is stored in Docker named volumes:

| Volume | Contents |
|--------|----------|
| `pgdata` | PostgreSQL database files |
| `logs` | Application logs |
| `uploads` | Submitted ID photos |
| `config` | Flask instance config overrides |

---

## Troubleshooting

### Containers won't start

Check the status and logs:

```bash
docker compose ps
docker compose logs flask
docker compose logs db
```

For the test stack substitute `docker compose -f docker-compose.test.yml`.

### Flask fails health check on startup

Usually a database connection issue. The most common cause after a re-clone is a stale postgres volume holding credentials from a previous `.env`. Fix by wiping the volume:

```bash
docker compose down -v
./deploy.sh --test   # regenerates .env and volumes
```

### Can't reach the app from another machine / SSH tunnel

1. Verify containers are running: `docker compose ps`
2. Check nginx is listening: `curl -sv http://localhost:8080/`
3. The HTTP port should redirect to HTTPS — if it redirects to port 443 instead of your configured `HTTPS_PORT`, regenerate the nginx config by rerunning the deploy script
4. For SSH tunnels, forward both ports: `ssh -L 8443:localhost:8443 -L 8080:localhost:8080 user@server`
5. If another process on your **local machine** already owns the forwarded port, SSH will silently drop that tunnel — check with `lsof -i :<port>` on your local machine

### Browser shows ERR_SSL_KEY_USAGE_INCOMPATIBLE

The TLS certificate was generated with incorrect key usage flags. Delete the cert and redeploy — the script will regenerate it:

```bash
rm docker/nginx/certs/cert.pem docker/nginx/certs/key.pem
./deploy.sh --update
```

### 500 error in the admin panel

Pull the traceback from the Flask logs:

```bash
docker compose logs flask --tail 50
# or for the test stack:
docker compose -f docker-compose.test.yml logs flask_test --tail 50
```

### CSRF error on login

This usually means the session cookie was not set before the form was submitted. Common causes:

- The browser rejected the TLS certificate (check for cert errors before the login page loaded)
- The HTTP→HTTPS redirect is sending the browser to the wrong port (check nginx logs)

### Password reset email not arriving

Check MailHog in the test stack (`http://localhost:8025`) or your SMTP server logs in production. Verify `MAIL_*` variables in `.env` are correct and the SMTP server is reachable from inside the container:

```bash
docker compose exec flask ping -c 2 <MAIL_SERVER>
```

### Forgot admin password

Use the forgot password flow at `https://yourdomain/admin` → "Trouble signing in?". If email is not working, generate a reset link manually:

```bash
docker compose exec flask python3 - <<'EOF'
from app import create_app
from services import Database, AuthService
app = create_app()
with app.app_context():
    db = app.db
    auth = app.auth_service
    url, token = auth.gen_random_forgot_password_link()
    from hashlib import sha256
    hashed = sha256(token.encode()).hexdigest()
    row = db.execute_query("SELECT id FROM admins WHERE username=%s", ("yourusername",), fetch_one=True)
    db.execute_query("INSERT INTO admin_forgot_password (user_id, token, expire_after) VALUES (%s, %s, now() + interval '24 hours')", (row[0], hashed))
    print(url)
EOF
```

---

## Reporting a Bug

Open an issue at **https://github.com/l337glitchl337/idportal/issues** and include:

### Required information

**1. Steps to reproduce**
A numbered list of exact actions taken, starting from a fresh login.

**2. Expected behaviour**
What should have happened.

**3. Actual behaviour**
What happened instead. Include any error messages shown in the browser.

**4. Flask logs**

```bash
# Test stack
docker compose -f docker-compose.test.yml logs flask_test --tail 100

# Production
docker compose logs flask --tail 100
```

Paste the full output, not a screenshot. Tracebacks are especially important.

**5. Nginx logs** (for login issues, redirects, or 502 errors)

```bash
docker compose -f docker-compose.test.yml logs nginx_test --tail 50
```

**6. Environment**
- Deployment type: test stack or production
- Browser and version
- How you are accessing the app (direct, SSH tunnel, reverse proxy)
- Output of `docker compose ps`

### What not to include

Do not paste your `.env` file or any credentials. Redact passwords, secret keys, and client secrets before sharing any configuration.

---

## License

MIT — see [LICENSE](LICENSE).
