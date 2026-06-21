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

## Quick Start — Test Environment

The test stack runs the full application locally with OpenLDAP, MailHog, and a self-signed TLS certificate. No configuration required.

```bash
git clone https://github.com/l337glitchl337/idportal.git
cd idportal
./deploy.sh --test
```

The script will:

- Generate a `.env` with randomised secrets
- Issue a self-signed TLS certificate
- Build and start all containers
- Create a default super admin account and print a one-time password reset link

**Default test ports** (override in `.env` if they conflict):

| Service | URL |
|---------|-----|
| Portal | `https://localhost:8443` |
| Admin panel | `https://localhost:8443/admin` |
| MailHog (email capture) | `http://localhost:8025` |
| HTTP redirect | `http://localhost:8080` → `https://localhost:8443` |

Your browser will show a self-signed certificate warning — this is expected. Proceed past it.

**Test LDAP credentials:** `testuser@dev.local` / `TestPass123!`

### Port configuration

Edit `.env` before (re-)deploying to change the default ports:

```env
HTTPS_PORT=8443
HTTP_PORT=8080
MAILHOG_PORT=8025
```

The URL variables in `.env` update automatically on the next deploy.

### Updating the test stack

Pull the latest code and redeploy:

```bash
git pull
./deploy.sh --update
```

---

## Production Deployment

```bash
git clone https://github.com/l337glitchl337/idportal.git
cd idportal
./deploy.sh
```

On first run the script creates a `.env` template and exits. Fill in every `CHANGE_ME` value, then run `./deploy.sh` again to continue.

### Required environment variables

**Database**
```env
POSTGRES_DB=idportal
POSTGRES_USER=idportal
POSTGRES_PASSWORD=<strong password>
POSTGRES_HOST=db
POSTGRES_PORT=5432
```

**Flask**
```env
SECRET_KEY=<64+ character random string>
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
# JSON map of display labels to AD attribute names
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

The deploy script verifies the certificate on every run and will not start if it is missing or expired.

### Updating production

To apply code or dependency updates to an existing production installation:

```bash
./deploy.sh --update
```

The script will:

1. Check whether your local branch is behind origin and offer to run `git pull`
2. Take a compressed database backup to `backups/` before touching anything
3. Rebuild the Docker images with the latest code and packages
4. Restart the containers

Backups are retained automatically — the 10 most recent are kept and older ones are removed.

If the backup fails the script will warn you and ask for confirmation before continuing. Do not skip this unless you have another backup strategy in place.

To start completely fresh (wipe all data and reconfigure):

```bash
docker compose down -v   # stops containers and deletes volumes
rm .env                  # remove existing config
./deploy.sh           # runs as a fresh install
```

### First admin account

On first deploy the script detects no admin accounts and prompts you to create the initial super admin. A one-time password reset link is printed — open it to set the password. Subsequent deploys skip this step.

---

## Microsoft Entra ID (OAuth)

An optional "Sign in with Microsoft" button can be enabled on both the user and admin login pages.

### Entra app registration

1. Azure Portal → Entra ID → App registrations → New registration
2. Supported account types: **Single tenant**
3. Add a redirect URI (Web): `https://yourdomain/oauth/callback`
4. Copy **Application (client) ID** and **Directory (tenant) ID**
5. Certificates & secrets → New client secret → copy the value

### Environment variables

```env
ENTRA_CLIENT_ID=<application id>
ENTRA_CLIENT_SECRET=<client secret>
ENTRA_TENANT_ID=<directory id>
```

Leave these blank or unset to disable the feature. The button will not appear on the login pages when they are not configured.

### Admin provisioning

Admin accounts must be created in the admin panel before an Entra login will be accepted. A user who signs in with a Microsoft account that has no matching email in the `admins` table will be blocked with an error message.

---

## Data locations

All persistent data is stored in Docker named volumes:

| Volume | Contents |
|--------|----------|
| `pgdata` | PostgreSQL database files |
| `logs` | Application logs |
| `uploads` | Submitted ID photos |
| `config` | Flask instance config overrides |

---

## License

MIT — see [LICENSE](LICENSE).
