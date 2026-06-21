#!/usr/bin/env bash
# IDPortal production deploy script.
# Usage:
#   ./deploy.sh              # auto-detect: fresh install if .env missing, update otherwise
#   ./deploy.sh --update     # rebuild + restart existing install (prompts if behind origin)
#   ./deploy.sh --no-cache   # force full Docker layer rebuild
#   ./deploy.sh --test       # full prod stack + MailHog + OpenLDAP on ports 8080/8443
#
# Fresh install:
#   1. Run ./deploy.sh  →  .env is created; fill in every CHANGE_ME value
#   2. Run ./deploy.sh  →  builds, deploys, then walks you through first admin setup
#
# To start completely fresh: stop containers, delete .env, re-run step 1.
set -euo pipefail

# ─── Output helpers ───────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; BOLD='\033[1m'; RESET='\033[0m'
info()  { echo -e "${CYAN}[INFO]${RESET}  $*"; }
ok()    { echo -e "${GREEN}[ OK ]${RESET}  $*"; }
warn()  { echo -e "${YELLOW}[WARN]${RESET}  $*"; }
error() { echo -e "${RED}[ERR ]${RESET}  $*" >&2; }
die()   { error "$*"; exit 1; }
step()  { echo; echo -e "${BOLD}── $* ──${RESET}"; }

# ─── Paths ────────────────────────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

COMPOSE_FILE="docker-compose.yml"
ENV_FILE=".env"
CERTS_DIR="docker/nginx/certs"

# Container names (must match docker-compose.yml)
CTR_FLASK="flask"
CTR_DB="postgres_db"
CTR_NGINX="nginx_proxy"

# ─── CLI flags ────────────────────────────────────────────────────────────────
MODE="auto"        # auto | update
BUILD_ARGS=""
TEST_MODE=false

for arg in "$@"; do
    case "$arg" in
        --update)    MODE="update" ;;
        --no-cache)  BUILD_ARGS="--no-cache" ;;
        --test)      TEST_MODE=true ;;
        --help|-h)
            sed -n '2,10p' "$0" | sed 's/^# //'
            exit 0
            ;;
        *) die "Unknown argument: $arg  (run $0 --help)" ;;
    esac
done

if $TEST_MODE; then
    COMPOSE_FILE="docker-compose.test.yml"
    CTR_FLASK="flask_test"
    CTR_DB="postgres_test"
    CTR_NGINX="nginx_test"
    [[ -f "$COMPOSE_FILE" ]] || die "$COMPOSE_FILE not found (it is gitignored — check that the file exists locally)."
fi

# ─── Prerequisites ────────────────────────────────────────────────────────────
check_prerequisites() {
    step "Checking prerequisites"
    local missing=()
    for cmd in docker openssl python3; do
        command -v "$cmd" &>/dev/null || missing+=("$cmd")
    done
    docker compose version &>/dev/null || missing+=("docker-compose-plugin")
    [[ ${#missing[@]} -eq 0 ]] || die "Missing required tools: ${missing[*]}"
    [[ -f "$COMPOSE_FILE" ]] || die "Run this script from the repo root ($COMPOSE_FILE not found)"
    ok "All prerequisites met"
}

# ─── .env helpers ─────────────────────────────────────────────────────────────
env_get() { grep -E "^${1}=" "$ENV_FILE" 2>/dev/null | cut -d= -f2- || true; }

REQUIRED_VARS=(
    SECRET_KEY
    POSTGRES_DB POSTGRES_USER POSTGRES_PASSWORD POSTGRES_HOST POSTGRES_PORT
    LDAP_URI LDAP_BIND_DN LDAP_BIND_PWD LDAP_SEARCH_BASE LDAP_SEARCH_FILTER LDAP_USE_TLS
    LDAP_ATTRIBUTES
    MAIL_SERVER MAIL_PORT MAIL_FROM_NAME MAIL_FROM_ADDRESS MAIL_DEFAULT_RECIP
    FORGOT_PASSWORD_URL SITE_TITLE LOGO
    USER_LOGIN_URL REVIEW_REQUEST_URL ADMIN_URL
    COMPANY_NAME COMPANY_ADDRESS COMPANY_STATE_ZIP COMPANY_PHONE
    COMPANY_CURRENT_YEAR COMPANY_EMAIL_SIGNATURE
)

validate_env() {
    step "Validating environment"
    [[ -f "$ENV_FILE" ]] || die "$ENV_FILE not found. Run ./deploy.sh without flags to start setup."

    local missing=() unfilled=()
    for var in "${REQUIRED_VARS[@]}"; do
        local val
        val=$(env_get "$var")
        if [[ -z "$val" ]]; then
            missing+=("$var")
        elif [[ "$val" == *"CHANGE_ME"* ]]; then
            unfilled+=("$var")
        fi
    done

    if [[ ${#missing[@]} -gt 0 ]]; then
        error "Missing variables in $ENV_FILE (add these):"
        for v in "${missing[@]}"; do echo "    $v"; done
        echo
    fi
    if [[ ${#unfilled[@]} -gt 0 ]]; then
        error "These variables still have placeholder values in $ENV_FILE:"
        for v in "${unfilled[@]}"; do echo "    $v = $(env_get "$v")"; done
        echo
    fi
    [[ ${#missing[@]} -eq 0 && ${#unfilled[@]} -eq 0 ]] || \
        die "Fix the above in $ENV_FILE and re-run."

    ok "All required variables are set"
}

# ─── First-time .env setup ────────────────────────────────────────────────────
setup_env() {
    step "Environment setup"
    if [[ -f "$ENV_FILE" ]]; then
        warn ".env already exists — skipping generation"
        warn "To start over: stop containers, delete .env, then re-run this script"
        return
    fi

    info "Generating secrets and creating $ENV_FILE..."
    local secret_key postgres_password
    secret_key=$(python3 -c "import secrets; print(secrets.token_urlsafe(64))")
    postgres_password=$(python3 -c "import secrets; print(secrets.token_hex(32))")

    if $TEST_MODE; then
        # New .env means new credentials — wipe stale test volumes so postgres
        # doesn't reject the new password on startup.
        if docker volume ls --format '{{.Name}}' 2>/dev/null | grep -q 'pgdata_test'; then
            info "Removing stale test volumes (credentials are being regenerated)..."
            docker compose -f "$COMPOSE_FILE" down -v 2>/dev/null || true
        fi

        cat > "$ENV_FILE" <<EOF
# Generated by deploy.sh --test on $(date '+%Y-%m-%d %H:%M:%S')
# This file is pre-configured for the local test stack.

# ─── Flask ────────────────────────────────────────────────────────────────────
SECRET_KEY=${secret_key}

# ─── PostgreSQL ───────────────────────────────────────────────────────────────
POSTGRES_DB=idportal
POSTGRES_USER=idportal
POSTGRES_PASSWORD=${postgres_password}
POSTGRES_HOST=db
POSTGRES_PORT=5432

# ─── LDAP / Active Directory ──────────────────────────────────────────────────
LDAP_URI=ldap://ldap:389
LDAP_BIND_DN=cn=admin,dc=dev,dc=local
LDAP_BIND_PWD=devpassword
LDAP_SEARCH_BASE=ou=Users,dc=dev,dc=local
LDAP_SEARCH_FILTER=(mail=%s)
LDAP_ATTRIBUTES={"First Name":"givenName","Last Name":"sn","ID Number":"title","Location":"o","cn":"cn","Email":"mail"}
LDAP_USE_TLS=false

# ─── Test stack ports ─────────────────────────────────────────────────────────
# Change these if the defaults conflict with something already on your machine.
HTTPS_PORT=8443
HTTP_PORT=8080
MAILHOG_PORT=8025

# ─── Site URLs ────────────────────────────────────────────────────────────────
# Keep these in sync with HTTPS_PORT above.
USER_LOGIN_URL=https://localhost:8443
FORGOT_PASSWORD_URL=https://localhost:8443/forgot_password
REVIEW_REQUEST_URL=https://localhost:8443/admin_panel
ADMIN_URL=https://localhost:8443/admin

# ─── Branding ─────────────────────────────────────────────────────────────────
SITE_TITLE=IDPortal
LOGO=portal_logo.png
COMPANY_NAME=Test Company
COMPANY_ADDRESS=123 Test Street
COMPANY_STATE_ZIP=New York, NY 10001
COMPANY_PHONE=(555) 555-5555
COMPANY_CURRENT_YEAR=$(date +%Y)
COMPANY_EMAIL_SIGNATURE=IDPortal Test Team

# ─── Email (SMTP) ─────────────────────────────────────────────────────────────
MAIL_SERVER=mailhog
MAIL_PORT=1025
MAIL_USE_TLS=false
MAIL_USE_SSL=false
MAIL_FROM_NAME=IDPortal Test
MAIL_FROM_ADDRESS=noreply@test.local
MAIL_DEFAULT_RECIP=admin@test.local
EOF
        ok "$ENV_FILE created for test stack"
    else
        cat > "$ENV_FILE" <<EOF
# Generated by deploy.sh on $(date '+%Y-%m-%d %H:%M:%S')
# Replace every CHANGE_ME value before re-running deploy.sh.

# ─── Flask ────────────────────────────────────────────────────────────────────
SECRET_KEY=${secret_key}

# ─── PostgreSQL ───────────────────────────────────────────────────────────────
POSTGRES_DB=idportal
POSTGRES_USER=idportal
POSTGRES_PASSWORD=${postgres_password}
POSTGRES_HOST=db
POSTGRES_PORT=5432

# ─── LDAP / Active Directory ──────────────────────────────────────────────────
# LDAP_URI      — your AD server, e.g. ldap://ad.example.com:389
# LDAP_BIND_DN  — service account DN used to search the directory
# LDAP_BIND_PWD — service account password
# LDAP_SEARCH_BASE   — OU where user accounts live
# LDAP_SEARCH_FILTER — filter to find users; %s is replaced with the user's email at runtime
#                      e.g. (mail=%s) or (userPrincipalName=%s)
# LDAP_ATTRIBUTES    — JSON map of display labels to AD attribute names
# LDAP_USE_TLS       — true enables STARTTLS on ldap:// connections
#                      For LDAPS (port 636) set LDAP_URI=ldaps://host:636 and LDAP_USE_TLS=false
# LDAP_TLS_CACERTFILE — (optional) absolute path to CA cert PEM for private/enterprise CAs
#                       Required when your LDAP server uses a self-signed or internal CA cert
LDAP_URI=CHANGE_ME
LDAP_BIND_DN=CHANGE_ME
LDAP_BIND_PWD=CHANGE_ME
LDAP_SEARCH_BASE=CHANGE_ME
LDAP_SEARCH_FILTER=(mail=%s)
LDAP_ATTRIBUTES={"First Name":"givenName","Last Name":"sn","ID Number":"employeeID","Location":"physicalDeliveryOfficeName","cn":"cn","Email":"mail"}
LDAP_USE_TLS=false
#LDAP_TLS_CACERTFILE=/etc/ssl/certs/my-ca.pem

# ─── Site URLs ────────────────────────────────────────────────────────────────
# All four must be the public HTTPS URL of your server.
USER_LOGIN_URL=CHANGE_ME
FORGOT_PASSWORD_URL=CHANGE_ME/forgot_password
REVIEW_REQUEST_URL=CHANGE_ME/admin_panel
ADMIN_URL=CHANGE_ME/admin

# ─── Branding ─────────────────────────────────────────────────────────────────
SITE_TITLE=IDPortal
LOGO=portal_logo.png
COMPANY_NAME=CHANGE_ME
COMPANY_ADDRESS=CHANGE_ME
COMPANY_STATE_ZIP=CHANGE_ME
COMPANY_PHONE=CHANGE_ME
COMPANY_CURRENT_YEAR=$(date +%Y)
COMPANY_EMAIL_SIGNATURE=CHANGE_ME

# ─── Email (SMTP) ─────────────────────────────────────────────────────────────
# For an unauthenticated internal relay (port 25): leave MAIL_USE_TLS=false
#   and comment out MAIL_USERNAME / MAIL_PASSWORD.
# For authenticated SMTP (e.g. port 587 STARTTLS): set MAIL_USE_TLS=true
#   and fill in MAIL_USERNAME / MAIL_PASSWORD.
# For SSL/TLS-only (port 465): set MAIL_USE_SSL=true instead.
MAIL_SERVER=CHANGE_ME
MAIL_PORT=25
MAIL_USE_TLS=false
MAIL_USE_SSL=false
#MAIL_USERNAME=CHANGE_ME
#MAIL_PASSWORD=CHANGE_ME
MAIL_FROM_NAME=IDPortal
MAIL_FROM_ADDRESS=CHANGE_ME
MAIL_DEFAULT_RECIP=CHANGE_ME

# ─── Microsoft Entra OAuth (optional) ────────────────────────────────────────
# Leave blank to disable the "Sign in with Microsoft" button.
# Register an app in Entra, add https://yourdomain/oauth/callback as a
# redirect URI, and paste the values below.
ENTRA_CLIENT_ID=
ENTRA_CLIENT_SECRET=
ENTRA_TENANT_ID=

# ─── Authentication modes ─────────────────────────────────────────────────────
# Controls which login method is accepted.
#   ADMIN_AUTH_MODE: local | entra | both  (default: local)
#   USER_AUTH_MODE:  ldap  | entra | both  (default: ldap)
# Set to 'entra' to disable password/LDAP login and require Microsoft sign-in.
# Set to 'both' to allow either method.
ADMIN_AUTH_MODE=local
USER_AUTH_MODE=ldap
EOF

        ok "$ENV_FILE created with generated secrets"
        echo
        echo -e "${BOLD}Next steps:${RESET}"
        echo "  1. Edit $ENV_FILE and replace every CHANGE_ME value"
        echo "  2. Place your SSL certificate at:"
        echo "       $CERTS_DIR/cert.pem"
        echo "       $CERTS_DIR/key.pem"
        echo "  3. Re-run: $0"
        echo
        exit 0
    fi
}

# ─── SSL certificates ─────────────────────────────────────────────────────────
setup_certs() {
    step "SSL certificates"
    mkdir -p "$CERTS_DIR"

    if [[ -f "$CERTS_DIR/cert.pem" && -f "$CERTS_DIR/key.pem" ]]; then
        ok "Certificates found"
        local expiry days_left exp_epoch now_epoch
        expiry=$(openssl x509 -enddate -noout -in "$CERTS_DIR/cert.pem" 2>/dev/null \
                 | cut -d= -f2 || true)
        if [[ -n "$expiry" ]]; then
            exp_epoch=$(date -d "$expiry" +%s 2>/dev/null \
                        || date -j -f "%b %d %T %Y %Z" "$expiry" +%s 2>/dev/null \
                        || echo 0)
            now_epoch=$(date +%s)
            days_left=$(( (exp_epoch - now_epoch) / 86400 ))
            if [[ $days_left -le 30 ]]; then
                warn "Certificate expires in ${days_left} days — renew before it lapses"
            else
                ok "Certificate valid for ${days_left} more days"
            fi
        fi
        return
    fi

    if $TEST_MODE; then
        info "Test mode: auto-generating self-signed certificate..."
        _gen_selfsigned_cert
        ok "Self-signed certificate generated (365 days)"
        return
    fi

    echo
    echo -e "${YELLOW}  No SSL certificate found in ${CERTS_DIR}/${RESET}"
    echo
    echo "  For production: place your CA-signed cert and key here:"
    echo "    $CERTS_DIR/cert.pem"
    echo "    $CERTS_DIR/key.pem"
    echo
    echo "  For testing only: generate a self-signed certificate instead"
    echo "  (browsers will show a security warning — not suitable for production)"
    echo
    read -rp "  Generate self-signed cert for testing? [y/N]: " choice
    case "${choice,,}" in
        y|yes)
            _gen_selfsigned_cert
            ok "Self-signed certificate generated (365 days)"
            warn "Replace with a CA-signed cert before going live"
            ;;
        *)
            die "Place cert.pem and key.pem in $CERTS_DIR/ then re-run."
            ;;
    esac
}

_gen_selfsigned_cert() {
    local host_ip san openssl_conf
    host_ip=$(hostname -I 2>/dev/null | awk '{print $1}')
    san="DNS:localhost,IP:127.0.0.1"
    [[ -n "$host_ip" && "$host_ip" != "127.0.0.1" ]] && san="${san},IP:${host_ip}"

    openssl_conf=$(mktemp)
    cat > "$openssl_conf" <<SSLEOF
[req]
distinguished_name = req_dn
x509_extensions   = v3_req
prompt            = no
[req_dn]
C  = US
ST = State
L  = City
O  = IDPortal
CN = localhost
[v3_req]
subjectAltName      = ${san}
keyUsage            = digitalSignature, keyEncipherment
extendedKeyUsage    = serverAuth
SSLEOF

    openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
        -keyout "$CERTS_DIR/key.pem" \
        -out    "$CERTS_DIR/cert.pem" \
        -config "$openssl_conf" \
        2>/dev/null
    rm -f "$openssl_conf"
    chmod 600 "$CERTS_DIR/key.pem"
}

# ─── Git update check ─────────────────────────────────────────────────────────
check_git_status() {
    command -v git &>/dev/null || return 0
    [[ -d .git ]] || return 0
    git fetch origin --quiet 2>/dev/null || return 0

    local behind
    behind=$(git rev-list "HEAD..@{upstream}" --count 2>/dev/null || echo "0")
    if [[ "$behind" -gt 0 ]]; then
        echo
        warn "$behind commit(s) on origin haven't been pulled yet."
        warn "Running 'git pull' before deploying ensures you ship the latest changes."
        echo
        read -rp "  Pull latest changes now? [Y/n]: " confirm
        case "${confirm,,}" in
            n|no) warn "Continuing without pulling — make sure this is intentional" ;;
            *)
                git pull
                ok "Up to date"
                ;;
        esac
    else
        ok "Already up to date with origin"
    fi
}

# ─── Database backup (pre-update) ─────────────────────────────────────────────
backup_db() {
    docker ps --format '{{.Names}}' 2>/dev/null | grep -q "^${CTR_DB}$" || return 0

    step "Database backup"
    local backup_dir="backups"
    local timestamp; timestamp=$(date +%Y%m%d_%H%M%S)
    local backup_file="${backup_dir}/idportal_${timestamp}.sql.gz"
    mkdir -p "$backup_dir"

    info "Dumping database to ${backup_file}..."
    local db_user db_name
    db_user=$(env_get "POSTGRES_USER")
    db_name=$(env_get "POSTGRES_DB")

    if docker exec "$CTR_DB" pg_dump -U "$db_user" "$db_name" 2>/dev/null \
            | gzip > "$backup_file"; then
        ok "Backup saved: $backup_file"
    else
        rm -f "$backup_file"
        echo
        warn "Database backup FAILED before deployment."
        warn "Deploying without a backup means you cannot roll back if something goes wrong."
        echo
        read -rp "  Continue without a backup? [y/N]: " confirm
        [[ "${confirm,,}" == "y" ]] || die "Aborted. Investigate backup failure and retry."
        warn "Continuing without backup — you have been warned"
    fi

    # Retain only the 10 most recent backups
    ls -t "${backup_dir}"/idportal_*.sql.gz 2>/dev/null | tail -n +11 | xargs -r rm --
}

# ─── Build images ─────────────────────────────────────────────────────────────
build_images() {
    step "Building images"
    info "Running docker compose build ${BUILD_ARGS:+(${BUILD_ARGS})}..."
    # shellcheck disable=SC2086
    docker compose -f "$COMPOSE_FILE" build --pull $BUILD_ARGS
    ok "Images built"
}

# ─── Deploy ───────────────────────────────────────────────────────────────────
deploy() {
    step "Deploying containers"
    docker compose -f "$COMPOSE_FILE" up -d --remove-orphans
    ok "Containers started"
}

# ─── Wait for health check ────────────────────────────────────────────────────
wait_healthy() {
    local container="$1"
    local timeout="${2:-90}"
    local elapsed=0

    local has_health
    has_health=$(docker inspect --format='{{if .State.Health}}yes{{end}}' \
                 "$container" 2>/dev/null || true)
    if [[ -z "$has_health" ]]; then
        local state
        state=$(docker inspect --format='{{.State.Status}}' "$container" 2>/dev/null || echo "missing")
        [[ "$state" == "running" ]] && { ok "$container is running"; return; }
        die "$container is not running (state: $state)"
    fi

    info "Waiting for $container to be healthy (timeout: ${timeout}s)..."
    while true; do
        local status
        status=$(docker inspect --format='{{.State.Health.Status}}' \
                 "$container" 2>/dev/null || echo "missing")
        case "$status" in
            healthy)
                ok "$container is healthy"
                return 0
                ;;
            unhealthy)
                error "$container failed its health check"
                docker logs --tail 20 "$container" >&2 || true
                die "Deployment aborted. Run 'docker logs $container' for details."
                ;;
        esac
        [[ $elapsed -lt $timeout ]] || {
            error "$container did not become healthy within ${timeout}s"
            docker logs --tail 20 "$container" >&2 || true
            die "Deployment timed out."
        }
        sleep 3; elapsed=$((elapsed + 3))
        printf "  %s (%ds)...\r" "$status" "$elapsed"
    done
}

# ─── Post-deploy verification ─────────────────────────────────────────────────
verify() {
    step "Verifying deployment"
    local all_ok=true
    for ctr in "$CTR_FLASK" "$CTR_DB" "$CTR_NGINX"; do
        local state
        state=$(docker inspect --format='{{.State.Status}}' "$ctr" 2>/dev/null || echo "not found")
        if [[ "$state" == "running" ]]; then
            ok "$ctr: running"
        else
            error "$ctr: $state"
            all_ok=false
        fi
    done
    $all_ok || die "One or more containers are not running. Run: docker compose -f $COMPOSE_FILE logs"
}

# ─── First admin bootstrap ────────────────────────────────────────────────────
bootstrap_first_admin() {
    local db_user db_name
    db_user=$(env_get "POSTGRES_USER")
    db_name=$(env_get "POSTGRES_DB")

    local count
    count=$(docker exec "$CTR_DB" psql -U "$db_user" -d "$db_name" \
            -tAc "SELECT COUNT(*) FROM admins;" 2>/dev/null | tr -d '[:space:]' || echo "0")

    [[ "$count" == "0" ]] || { ok "Admin accounts already exist — skipping bootstrap"; return; }

    step "First admin account setup"
    local fn ln un em
    if $TEST_MODE; then
        fn="Test"; ln="Admin"; un="testadmin"; em="admin@test.local"
        echo "  Test mode: creating default super admin (testadmin / admin@test.local)"
        echo
    else
        echo "  No admin accounts found. Set up your first super admin now."
        echo
        read -rp "  First name : " fn
        read -rp "  Last name  : " ln
        read -rp "  Username   : " un
        read -rp "  Email      : " em
        echo
    fi

    # Generate hashed password + setup token inside the Flask container
    # (bcrypt and hashlib are available there; avoids host dependency)
    local creds
    creds=$(docker exec -i "$CTR_FLASK" python3 - <<'PYEOF'
import bcrypt, secrets, hashlib, uuid
pw = secrets.token_urlsafe(32).encode()
hashed = bcrypt.hashpw(pw, bcrypt.gensalt()).decode()
token = uuid.uuid4().hex
token_hash = hashlib.sha256(token.encode()).hexdigest()
print(hashed + "|" + token + "|" + token_hash)
PYEOF
)
    local hashed_pw token token_hash
    hashed_pw="${creds%%|*}"
    token="${creds#*|}"; token="${token%%|*}"
    token_hash="${creds##*|}"

    # Escape single quotes for SQL
    local fn_e ln_e un_e em_e pw_e
    fn_e="${fn//\'/\'\'}"; ln_e="${ln//\'/\'\'}"; un_e="${un//\'/\'\'}"
    em_e="${em//\'/\'\'}"; pw_e="${hashed_pw//\'/\'\'}"

    # Insert admin and get ID
    local user_id
    user_id=$(docker exec "$CTR_DB" psql -U "$db_user" -d "$db_name" -tAc \
        "INSERT INTO admins (first_name, last_name, username, email, role, password)
         VALUES ('${fn_e}', '${ln_e}', '${un_e}', '${em_e}', 'super', '${pw_e}')
         RETURNING id;" | head -1 | tr -d '[:space:]')

    # Insert 24-hour setup token
    docker exec "$CTR_DB" psql -U "$db_user" -d "$db_name" -c \
        "INSERT INTO admin_forgot_password (user_id, token, expire_after)
         VALUES (${user_id}, '${token_hash}', now() + interval '24 hours');" > /dev/null

    local forgot_url
    forgot_url=$(env_get "FORGOT_PASSWORD_URL")

    ok "Super admin '${un}' created"
    echo
    echo -e "  ${BOLD}${YELLOW}Set your password using this link (expires in 24 hours):${RESET}"
    echo -e "  ${CYAN}${forgot_url}?token=${token}${RESET}"
    echo
    warn "Save this link — it will not be shown again."
}

# ─── Generate test nginx config with correct redirect port ────────────────────
# nginx's $host strips the port, so "return 301 https://$host$request_uri"
# redirects to port 443 (default), not the mapped HTTPS port (e.g. 8443).
# We generate a test-specific config with the actual HTTPS port injected.
setup_nginx_test_config() {
    $TEST_MODE || return 0
    local https_port
    https_port=$(env_get "HTTPS_PORT" 2>/dev/null || echo "8443")
    sed 's|return 301 https://$host$request_uri|return 301 https://$host:'"${https_port}"'$request_uri|' \
        docker/nginx/nginx.ssl.conf > docker/nginx/nginx.test.conf
}

# ─── Sync test URLs to current HTTPS_PORT ─────────────────────────────────────
sync_test_urls() {
    $TEST_MODE || return 0
    local port
    port=$(env_get "HTTPS_PORT" 2>/dev/null || echo "8443")
    sed -i \
        -e "s|USER_LOGIN_URL=https://localhost:[0-9]*|USER_LOGIN_URL=https://localhost:${port}|" \
        -e "s|FORGOT_PASSWORD_URL=https://localhost:[0-9]*/forgot_password|FORGOT_PASSWORD_URL=https://localhost:${port}/forgot_password|" \
        -e "s|REVIEW_REQUEST_URL=https://localhost:[0-9]*/admin_panel|REVIEW_REQUEST_URL=https://localhost:${port}/admin_panel|" \
        -e "s|ADMIN_URL=https://localhost:[0-9]*/admin|ADMIN_URL=https://localhost:${port}/admin|" \
        "$ENV_FILE"
}

# ─── Summary ──────────────────────────────────────────────────────────────────
print_summary() {
    local cf_flag=""
    $TEST_MODE && cf_flag="-f $COMPOSE_FILE "

    echo
    echo -e "${GREEN}${BOLD}╔══════════════════════════════════╗${RESET}"
    echo -e "${GREEN}${BOLD}║     Deployment complete!         ║${RESET}"
    echo -e "${GREEN}${BOLD}╚══════════════════════════════════╝${RESET}"
    echo
    if $TEST_MODE; then
        local https_port http_port mailhog_port
        https_port=$(env_get "HTTPS_PORT" 2>/dev/null || echo "8443")
        http_port=$(env_get "HTTP_PORT" 2>/dev/null || echo "8080")
        mailhog_port=$(env_get "MAILHOG_PORT" 2>/dev/null || echo "8025")
        echo -e "  Portal  : ${CYAN}https://localhost:${https_port}${RESET}  (accept the self-signed cert warning)"
        echo -e "  Admin   : ${CYAN}https://localhost:${https_port}/admin${RESET}"
        echo -e "  MailHog : ${CYAN}http://localhost:${mailhog_port}${RESET}"
        echo -e "  HTTP    : http://localhost:${http_port}  →  redirects to ${https_port}"
        echo
        echo -e "  Test LDAP login: testuser@dev.local / TestPass123!"
    else
        local site_url admin_url
        site_url=$(env_get "USER_LOGIN_URL")
        admin_url=$(env_get "ADMIN_URL")
        echo -e "  Portal : ${CYAN}${site_url}${RESET}"
        echo -e "  Admin  : ${CYAN}${admin_url}${RESET}"
    fi
    echo
    echo -e "  Useful commands:"
    echo -e "    docker compose ${cf_flag}logs -f              # stream all logs"
    echo -e "    docker compose ${cf_flag}logs -f ${CTR_FLASK}  # stream app logs"
    echo -e "    docker compose ${cf_flag}ps                   # container status"
    echo -e "    docker compose ${cf_flag}down                 # stop everything"
    echo -e "    ./deploy.sh --update                       # upgrade to latest version"
    echo
}

# ─── Main ─────────────────────────────────────────────────────────────────────
main() {
    echo
    echo -e "${BOLD}╔══════════════════════════════════╗${RESET}"
    echo -e "${BOLD}║      IDPortal  ·  Deploy         ║${RESET}"
    echo -e "${BOLD}╚══════════════════════════════════╝${RESET}"
    echo

    check_prerequisites

    if [[ "$MODE" == "auto" ]]; then
        [[ -f "$ENV_FILE" ]] && MODE="update" || MODE="fresh"
    fi

    info "Mode: $MODE"

    if [[ "$MODE" == "fresh" ]]; then
        setup_env       # exits after writing .env stub if it didn't exist
        sync_test_urls
        validate_env
        setup_certs
    else
        check_git_status
        sync_test_urls
        validate_env
        setup_certs
        backup_db
    fi

    setup_nginx_test_config
    build_images
    deploy

    wait_healthy "$CTR_DB"    90
    wait_healthy "$CTR_FLASK" 90
    wait_healthy "$CTR_NGINX" 30

    verify
    bootstrap_first_admin
    print_summary
}

main "$@"
