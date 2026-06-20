#!/usr/bin/env bash
# IDPortal production deploy script.
# Usage:
#   ./deploy.sh              # auto-detect: fresh install if .env missing, update otherwise
#   ./deploy.sh --update     # rebuild + restart (skip setup wizard)
#   ./deploy.sh --fresh      # re-run first-time setup wizard
#   ./deploy.sh --no-cache   # pass through to docker build (forces full rebuild)
#   ./deploy.sh --test       # production stack + MailHog + OpenLDAP on ports 8080/8443
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
MODE="auto"        # auto | fresh | update
BUILD_ARGS=""
TEST_MODE=false

for arg in "$@"; do
    case "$arg" in
        --fresh)     MODE="fresh" ;;
        --update)    MODE="update" ;;
        --no-cache)  BUILD_ARGS="--no-cache" ;;
        --test)      TEST_MODE=true ;;
        --help|-h)
            sed -n '2,7p' "$0" | sed 's/^# //'
            exit 0
            ;;
        *) die "Unknown argument: $arg" ;;
    esac
done

if $TEST_MODE; then
    COMPOSE_FILE="docker-compose.test.yml"
    CTR_FLASK="flask_test"
    CTR_DB="postgres_test"
    CTR_NGINX="nginx_test"
    [[ -f "$COMPOSE_FILE" ]] || die "$COMPOSE_FILE not found. It may have been deleted (it is gitignored and not in the repo)."
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
    [[ -f "$COMPOSE_FILE" ]] || die "Run this script from the repo root (docker-compose.yml not found)"
    ok "All prerequisites met"
}

# ─── .env helpers ─────────────────────────────────────────────────────────────
env_get() { grep -E "^${1}=" "$ENV_FILE" 2>/dev/null | cut -d= -f2- || true; }

REQUIRED_VARS=(
    SECRET_KEY
    POSTGRES_DB POSTGRES_DBNAME POSTGRES_USER POSTGRES_PASSWORD POSTGRES_HOST POSTGRES_PORT
    LDAP_URI LDAP_BIND_DN LDAP_BIND_PWD LDAP_SEARCH_BASE LDAP_SEARCH_FILTER LDAP_USE_TLS
    MAIL_SERVER MAIL_PORT MAIL_FROM_NAME MAIL_FROM_ADDRESS MAIL_DEFAULT_RECIP
    FORGOT_PASSWORD_URL SITE_TITLE LOGO
    USER_LOGIN_URL REVIEW_REQUEST_URL ADMIN_URL
    COMPANY_NAME COMPANY_ADDRESS COMPANY_STATE_ZIP COMPANY_PHONE
    COMPANY_CURRENT_YEAR COMPANY_EMAIL_SIGNATURE
)

validate_env() {
    step "Validating environment"
    [[ -f "$ENV_FILE" ]] || die "$ENV_FILE not found. Run without --update for first-time setup."
    local missing=()
    for var in "${REQUIRED_VARS[@]}"; do
        [[ -n "$(env_get "$var")" ]] || missing+=("$var")
    done
    if [[ ${#missing[@]} -gt 0 ]]; then
        error "Missing required variables in $ENV_FILE:"
        for v in "${missing[@]}"; do echo "    $v"; done
        die "Fill in all required variables and re-run."
    fi
    ok "All required variables present"
}

# ─── First-time .env setup ────────────────────────────────────────────────────
setup_env() {
    step "Environment setup"
    if [[ -f "$ENV_FILE" ]]; then
        warn ".env already exists — skipping generation (delete it to start completely fresh)"
        return
    fi

    info "Generating secrets and creating $ENV_FILE..."
    local secret_key postgres_password
    secret_key=$(python3 -c "import secrets; print(secrets.token_urlsafe(64))")
    postgres_password=$(python3 -c "import secrets; print(secrets.token_hex(32))")

    cat > "$ENV_FILE" <<EOF
# ─── Flask ────────────────────────────────────────────────────────────────────
SECRET_KEY=${secret_key}

# ─── PostgreSQL ───────────────────────────────────────────────────────────────
POSTGRES_DB=idportal
POSTGRES_DBNAME=idportal
POSTGRES_USER=idportal
POSTGRES_PASSWORD=${postgres_password}
POSTGRES_HOST=db
POSTGRES_PORT=5432

# ─── LDAP / Active Directory ──────────────────────────────────────────────────
LDAP_URI=ldap://your-ad-server:389
LDAP_BIND_DN=CN=svc_idportal,OU=Service Accounts,DC=example,DC=com
LDAP_BIND_PWD=
LDAP_SEARCH_BASE=OU=Users,DC=example,DC=com
LDAP_SEARCH_FILTER=(mail=OBJ)
LDAP_ATTRIBUTES={"First Name":"givenName","Last Name":"sn","ID Number":"employeeID","Location":"physicalDeliveryOfficeName","cn":"cn","Email":"mail"}
LDAP_USE_TLS=False

# ─── Branding ─────────────────────────────────────────────────────────────────
SITE_TITLE=IDPortal
LOGO=portal_logo.png
USER_LOGIN_URL=https://yourdomain.com
FORGOT_PASSWORD_URL=https://yourdomain.com/forgot_password
REVIEW_REQUEST_URL=https://yourdomain.com/admin_panel
ADMIN_URL=https://yourdomain.com/admin
COMPANY_NAME=Your Company
COMPANY_ADDRESS=123 Main Street
COMPANY_STATE_ZIP=City, ST 00000
COMPANY_PHONE=(555) 555-5555
COMPANY_CURRENT_YEAR=$(date +%Y)
COMPANY_EMAIL_SIGNATURE=The IDPortal Team

# ─── Email (SMTP) ─────────────────────────────────────────────────────────────
MAIL_SERVER=smtp.yourdomain.com
MAIL_PORT=587
MAIL_FROM_NAME=IDPortal
MAIL_FROM_ADDRESS=noreply@yourdomain.com
MAIL_DEFAULT_RECIP=idportal-admin@yourdomain.com
EOF

    ok "$ENV_FILE created with generated secrets"
    echo
    warn "ACTION REQUIRED: Edit $ENV_FILE and fill in all empty/placeholder values."
    warn "When done, re-run: $0"
    exit 0
}

# ─── SSL certificates ─────────────────────────────────────────────────────────
setup_certs() {
    step "SSL certificates"
    mkdir -p "$CERTS_DIR"

    if [[ -f "$CERTS_DIR/cert.pem" && -f "$CERTS_DIR/key.pem" ]]; then
        ok "Certificates found"
        # Warn if expiring within 30 days
        local expiry days_left
        expiry=$(openssl x509 -enddate -noout -in "$CERTS_DIR/cert.pem" 2>/dev/null \
                 | cut -d= -f2 || true)
        if [[ -n "$expiry" ]]; then
            local exp_epoch now_epoch
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
        openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
            -keyout "$CERTS_DIR/key.pem" \
            -out   "$CERTS_DIR/cert.pem" \
            -subj  "/C=US/ST=State/L=City/O=IDPortal/CN=localhost" \
            2>/dev/null
        chmod 600 "$CERTS_DIR/key.pem"
        ok "Self-signed certificate generated (365 days)"
        return
    fi

    echo
    echo -e "  No certificate found in ${CYAN}${CERTS_DIR}/${RESET}"
    echo "  Options:"
    echo "    1) I will copy cert.pem / key.pem to $CERTS_DIR/ manually (then re-run)"
    echo "    2) Generate a self-signed certificate (not trusted by browsers — testing only)"
    echo
    read -rp "  Choice [1/2]: " choice
    case "$choice" in
        1) die "Copy your cert.pem and key.pem to $CERTS_DIR/ then re-run." ;;
        2)
            openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
                -keyout "$CERTS_DIR/key.pem" \
                -out   "$CERTS_DIR/cert.pem" \
                -subj  "/C=US/ST=State/L=City/O=IDPortal/CN=localhost" \
                2>/dev/null
            chmod 600 "$CERTS_DIR/key.pem"
            ok "Self-signed certificate generated (365 days)"
            warn "Self-signed certs trigger browser warnings — use a CA-signed cert for production"
            ;;
        *) die "Invalid choice" ;;
    esac
}

# ─── Database backup (pre-update) ─────────────────────────────────────────────
backup_db() {
    # Only run if the DB container is already up
    if ! docker ps --format '{{.Names}}' 2>/dev/null | grep -q "^${CTR_DB}$"; then
        return
    fi
    step "Database backup"
    local backup_dir="backups"
    local timestamp; timestamp=$(date +%Y%m%d_%H%M%S)
    local backup_file="${backup_dir}/idportal_${timestamp}.sql.gz"
    mkdir -p "$backup_dir"

    info "Dumping database to ${backup_file}..."
    local db_user; db_user=$(env_get "POSTGRES_USER")
    local db_name; db_name=$(env_get "POSTGRES_DBNAME")

    if docker exec "$CTR_DB" pg_dump -U "$db_user" "$db_name" \
            2>/dev/null | gzip > "$backup_file"; then
        ok "Backup saved: $backup_file"
    else
        warn "Database backup failed — continuing, but proceed with caution"
        rm -f "$backup_file"
    fi

    # Keep only the 10 most recent backups
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

    # If the container has no healthcheck, just confirm it's running
    local has_health
    has_health=$(docker inspect --format='{{if .State.Health}}yes{{end}}' \
                 "$container" 2>/dev/null || true)
    if [[ -z "$has_health" ]]; then
        local state
        state=$(docker inspect --format='{{.State.Status}}' "$container" 2>/dev/null || echo "missing")
        [[ "$state" == "running" ]] && { ok "$container is running"; return; }
        die "$container is not running (state: $state)"
    fi

    info "Waiting for $container to pass health check (timeout: ${timeout}s)..."
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
                error "$container failed health check"
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
        printf "  %s (%ds elapsed)...\r" "$status" "$elapsed"
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
    $all_ok || die "One or more containers are not running. Run: docker compose logs"
}

# ─── Summary ──────────────────────────────────────────────────────────────────
print_summary() {
    echo
    echo -e "${GREEN}${BOLD}╔══════════════════════════════════╗${RESET}"
    echo -e "${GREEN}${BOLD}║   Deployment complete!           ║${RESET}"
    echo -e "${GREEN}${BOLD}╚══════════════════════════════════╝${RESET}"
    echo
    if $TEST_MODE; then
        echo -e "  User portal : ${CYAN}https://localhost:8443${RESET}  (self-signed — accept the browser warning)"
        echo -e "  Admin panel : ${CYAN}https://localhost:8443/admin${RESET}"
        echo -e "  MailHog     : ${CYAN}http://localhost:8025${RESET}"
        echo -e "  HTTP        : ${CYAN}http://localhost:8080${RESET}  → redirects to 8443"
        echo
        echo -e "  Test credentials (LDAP): testuser@dev.local / TestPass123!"
    else
        local site_url admin_url
        site_url=$(env_get "USER_LOGIN_URL")
        admin_url=$(env_get "ADMIN_URL")
        echo -e "  User portal : ${CYAN}${site_url}${RESET}"
        echo -e "  Admin panel : ${CYAN}${admin_url}${RESET}"
    fi
    echo
    local cf_flag=""
    $TEST_MODE && cf_flag="-f $COMPOSE_FILE "
    echo -e "  Useful commands:"
    echo -e "    docker compose ${cf_flag}logs -f              # tail all logs"
    echo -e "    docker compose ${cf_flag}logs -f ${CTR_FLASK}  # tail app logs"
    echo -e "    docker compose ${cf_flag}ps                   # container status"
    echo -e "    docker compose ${cf_flag}down                 # stop all services"
    echo
}

# ─── Main ─────────────────────────────────────────────────────────────────────
main() {
    echo
    echo -e "${BOLD}╔══════════════════════════════════╗${RESET}"
    echo -e "${BOLD}║     IDPortal  ·  Deploy          ║${RESET}"
    echo -e "${BOLD}╚══════════════════════════════════╝${RESET}"
    echo

    check_prerequisites

    if [[ "$MODE" == "auto" ]]; then
        [[ -f "$ENV_FILE" ]] && MODE="update" || MODE="fresh"
    fi

    info "Mode: $MODE"

    if [[ "$MODE" == "fresh" ]]; then
        setup_env       # exits after creating .env stub if it didn't exist
        validate_env
        setup_certs
    else
        validate_env
        setup_certs
        backup_db
    fi

    build_images
    deploy

    wait_healthy "$CTR_DB"    90
    wait_healthy "$CTR_FLASK" 90
    wait_healthy "$CTR_NGINX" 30

    verify
    print_summary
}

main "$@"
