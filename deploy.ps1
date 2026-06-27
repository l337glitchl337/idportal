<#
.SYNOPSIS
    IDPortal production deploy script for Windows (PowerShell).
.DESCRIPTION
    Usage:
      .\deploy.ps1              # auto-detect: fresh install if .env missing, update otherwise
      .\deploy.ps1 -Update      # rebuild + restart existing install (prompts if behind origin)
      .\deploy.ps1 -NoCache     # force full Docker layer rebuild
      .\deploy.ps1 -Test        # full prod stack + MailHog + OpenLDAP on ports 8080/8443

    Fresh install:
      1. Run .\deploy.ps1  ->  .env is created; fill in every CHANGE_ME value
      2. Run .\deploy.ps1  ->  builds, deploys, then walks you through first admin setup

    Requires: Docker Desktop, PowerShell 5.1+, Python 3, Git for Windows (provides openssl)

    If you get "running scripts is disabled", run once as Administrator:
      Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
#>
[CmdletBinding()]
param(
    [switch]$Update,
    [switch]$NoCache,
    [switch]$Test,
    [switch]$Help
)

$ErrorActionPreference = 'Stop'

if ($Help) { Get-Help $MyInvocation.MyCommand.Path -Detailed; exit 0 }

# ─── Output helpers ───────────────────────────────────────────────────────────
function Write-Info($msg)  { Write-Host "[INFO]  $msg" -ForegroundColor Cyan }
function Write-Ok($msg)    { Write-Host "[ OK ]  $msg" -ForegroundColor Green }
function Write-Warn($msg)  { Write-Host "[WARN]  $msg" -ForegroundColor Yellow }
function Write-Err($msg)   { Write-Host "[ERR ]  $msg" -ForegroundColor Red }
function Write-Step($msg)  { Write-Host "`n── $msg ──" -ForegroundColor White }
function Die($msg)         { Write-Err $msg; exit 1 }

# ─── Paths ────────────────────────────────────────────────────────────────────
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ScriptDir

$ComposeFile = "docker-compose.yml"
$EnvFile     = ".env"
$CertsDir    = "docker\nginx\certs"
$CtrFlask    = "flask"
$CtrDb       = "postgres_db"
$CtrNginx    = "nginx_proxy"

if ($Test) {
    $ComposeFile = "docker-compose.test.yml"
    $CtrFlask    = "flask_test"
    $CtrDb       = "postgres_test"
    $CtrNginx    = "nginx_test"
    if (-not (Test-Path $ComposeFile)) {
        Die "$ComposeFile not found — check that the file exists locally."
    }
}

$BuildArgs = if ($NoCache) { "--no-cache" } else { $null }
$Mode      = if ($Update)  { "update" }    else { "auto" }

# ─── .env helpers ─────────────────────────────────────────────────────────────
function Get-EnvValue($key) {
    if (-not (Test-Path $EnvFile)) { return $null }
    $line = Get-Content $EnvFile | Where-Object { $_ -match "^${key}=" } | Select-Object -First 1
    if ($line) { return $line.Substring($key.Length + 1) }
    return $null
}

function Update-EnvValue($key, $value) {
    $content = Get-Content $EnvFile
    $content = $content -replace "^${key}=.*", "${key}=${value}"
    Set-Content $EnvFile $content -Encoding UTF8
}

# ─── Prerequisites ────────────────────────────────────────────────────────────
$script:Python  = $null
$script:OpenSSL = $null

function Check-Prerequisites {
    Write-Step "Checking prerequisites"
    $missing = @()

    if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
        $missing += "docker (install Docker Desktop from https://www.docker.com/products/docker-desktop)"
    } else {
        try { docker compose version 2>&1 | Out-Null }
        catch { $missing += "docker compose plugin (update Docker Desktop)" }
    }

    foreach ($py in @("python3", "python", "py")) {
        if (Get-Command $py -ErrorAction SilentlyContinue) {
            $script:Python = $py; break
        }
    }
    if (-not $script:Python) {
        $missing += "python3 (install from https://www.python.org/downloads/)"
    }

    $opensslCandidates = @(
        "openssl",
        "C:\Program Files\Git\usr\bin\openssl.exe",
        "C:\Program Files (x86)\Git\usr\bin\openssl.exe",
        "$env:ProgramFiles\Git\usr\bin\openssl.exe"
    )
    foreach ($c in $opensslCandidates) {
        if (Get-Command $c -ErrorAction SilentlyContinue) {
            $script:OpenSSL = $c; break
        }
    }
    if (-not $script:OpenSSL) {
        $missing += "openssl (install Git for Windows from https://git-scm.com/download/win)"
    }

    if (-not (Test-Path $ComposeFile)) {
        $missing += "$ComposeFile not found — run this script from the repo root"
    }

    if ($missing.Count -gt 0) {
        Write-Err "Missing required tools:"
        $missing | ForEach-Object { Write-Host "    - $_" }
        exit 1
    }
    Write-Ok "All prerequisites met"
}

# ─── Required vars ────────────────────────────────────────────────────────────
$RequiredVars = @(
    "SECRET_KEY",
    "POSTGRES_DB", "POSTGRES_USER", "POSTGRES_PASSWORD", "POSTGRES_HOST", "POSTGRES_PORT",
    "LDAP_URI", "LDAP_BIND_DN", "LDAP_BIND_PWD", "LDAP_SEARCH_BASE",
    "LDAP_SEARCH_FILTER", "LDAP_USE_TLS", "LDAP_ATTRIBUTES",
    "MAIL_SERVER", "MAIL_PORT", "MAIL_FROM_NAME", "MAIL_FROM_ADDRESS", "MAIL_DEFAULT_RECIP",
    "FORGOT_PASSWORD_URL", "SITE_TITLE", "LOGO",
    "USER_LOGIN_URL", "REVIEW_REQUEST_URL", "ADMIN_URL",
    "COMPANY_NAME", "COMPANY_ADDRESS", "COMPANY_STATE_ZIP", "COMPANY_PHONE",
    "COMPANY_CURRENT_YEAR", "COMPANY_EMAIL_SIGNATURE"
)

function Validate-Env {
    Write-Step "Validating environment"
    if (-not (Test-Path $EnvFile)) {
        Die "$EnvFile not found. Run .\deploy.ps1 without flags to start setup."
    }
    $missing = @(); $unfilled = @()
    foreach ($var in $RequiredVars) {
        $val = Get-EnvValue $var
        if (-not $val)                { $missing  += $var }
        elseif ($val -like "*CHANGE_ME*") { $unfilled += "$var = $val" }
    }
    if ($missing.Count -gt 0) {
        Write-Err "Missing variables in ${EnvFile}:"
        $missing | ForEach-Object { Write-Host "    $_" }
        Write-Host ""
    }
    if ($unfilled.Count -gt 0) {
        Write-Err "These variables still have placeholder values:"
        $unfilled | ForEach-Object { Write-Host "    $_" }
        Write-Host ""
    }
    if ($missing.Count -gt 0 -or $unfilled.Count -gt 0) {
        Die "Fix the above in $EnvFile and re-run."
    }
    Write-Ok "All required variables are set"
}

# ─── First-time .env setup ────────────────────────────────────────────────────
function Setup-Env {
    Write-Step "Environment setup"
    if (Test-Path $EnvFile) {
        Write-Warn ".env already exists — skipping generation"
        Write-Warn "To start over: stop containers, delete .env, then re-run this script"
        return
    }

    Write-Info "Generating secrets and creating $EnvFile..."
    $secretKey        = & $script:Python -c "import secrets; print(secrets.token_urlsafe(64))"
    $postgresPassword = & $script:Python -c "import secrets; print(secrets.token_hex(32))"
    $year             = (Get-Date).Year
    $timestamp        = Get-Date -Format "yyyy-MM-dd HH:mm:ss"

    if ($Test) {
        $vol = docker volume ls --format '{{.Name}}' 2>$null | Where-Object { $_ -match 'pgdata_test' }
        if ($vol) {
            Write-Info "Removing stale test volumes (credentials are being regenerated)..."
            docker compose -f $ComposeFile down -v 2>$null
        }

        @"
# Generated by deploy.ps1 -Test on $timestamp
# This file is pre-configured for the local test stack.

# --- Flask -------------------------------------------------------------------
SECRET_KEY=$secretKey

# --- PostgreSQL --------------------------------------------------------------
POSTGRES_DB=idportal
POSTGRES_USER=idportal
POSTGRES_PASSWORD=$postgresPassword
POSTGRES_HOST=db
POSTGRES_PORT=5432

# --- LDAP / Active Directory -------------------------------------------------
LDAP_URI=ldap://ldap:389
LDAP_BIND_DN=cn=admin,dc=dev,dc=local
LDAP_BIND_PWD=devpassword
LDAP_SEARCH_BASE=ou=Users,dc=dev,dc=local
LDAP_SEARCH_FILTER=(mail=%s)
LDAP_ATTRIBUTES={"First Name":"givenName","Last Name":"sn","ID Number":"title","Location":"o","cn":"cn","Email":"mail"}
LDAP_USE_TLS=false

# --- Test stack ports --------------------------------------------------------
HTTPS_PORT=8443
HTTP_PORT=8080
MAILHOG_PORT=8025

# --- Site URLs ---------------------------------------------------------------
USER_LOGIN_URL=https://localhost:8443
FORGOT_PASSWORD_URL=https://localhost:8443/forgot_password
REVIEW_REQUEST_URL=https://localhost:8443/admin_panel
ADMIN_URL=https://localhost:8443/admin

# --- Branding ----------------------------------------------------------------
SITE_TITLE=IDPortal
LOGO=portal_logo.png
COMPANY_NAME=Test Company
COMPANY_ADDRESS=123 Test Street
COMPANY_STATE_ZIP=New York, NY 10001
COMPANY_PHONE=(555) 555-5555
COMPANY_CURRENT_YEAR=$year
COMPANY_EMAIL_SIGNATURE=IDPortal Test Team

# --- Email (SMTP) ------------------------------------------------------------
MAIL_SERVER=mailhog
MAIL_PORT=1025
MAIL_USE_TLS=false
MAIL_USE_SSL=false
MAIL_FROM_NAME=IDPortal Test
MAIL_FROM_ADDRESS=noreply@test.local
MAIL_DEFAULT_RECIP=admin@test.local

# --- Authentication modes ----------------------------------------------------
ADMIN_AUTH_MODE=local
USER_AUTH_MODE=ldap

# --- Microsoft Entra OAuth (optional) ----------------------------------------
ENTRA_CLIENT_ID=
ENTRA_CLIENT_SECRET=
ENTRA_TENANT_ID=
"@ | Set-Content $EnvFile -Encoding UTF8
        Write-Ok "$EnvFile created for test stack"

    } else {
        @"
# Generated by deploy.ps1 on $timestamp
# Replace every CHANGE_ME value before re-running deploy.ps1.

# --- Flask -------------------------------------------------------------------
SECRET_KEY=$secretKey

# --- PostgreSQL --------------------------------------------------------------
POSTGRES_DB=idportal
POSTGRES_USER=idportal
POSTGRES_PASSWORD=$postgresPassword
POSTGRES_HOST=db
POSTGRES_PORT=5432

# --- LDAP / Active Directory -------------------------------------------------
# LDAP_URI      - your AD server, e.g. ldap://ad.example.com:389
# LDAP_BIND_DN  - service account DN used to search the directory
# LDAP_BIND_PWD - service account password
# LDAP_SEARCH_FILTER - filter to find users; %s is replaced with the user's email
# LDAP_USE_TLS  - true enables STARTTLS on ldap:// connections
#                 For LDAPS (port 636) set LDAP_URI=ldaps://host:636 and LDAP_USE_TLS=false
# LDAP_TLS_CACERTFILE - (optional) path to CA cert PEM for private/enterprise CAs
LDAP_URI=CHANGE_ME
LDAP_BIND_DN=CHANGE_ME
LDAP_BIND_PWD=CHANGE_ME
LDAP_SEARCH_BASE=CHANGE_ME
LDAP_SEARCH_FILTER=(mail=%s)
LDAP_ATTRIBUTES={"First Name":"givenName","Last Name":"sn","ID Number":"employeeID","Location":"physicalDeliveryOfficeName","cn":"cn","Email":"mail"}
LDAP_USE_TLS=false
#LDAP_TLS_CACERTFILE=C:\path\to\ca.pem

# --- Site URLs ---------------------------------------------------------------
USER_LOGIN_URL=CHANGE_ME
FORGOT_PASSWORD_URL=CHANGE_ME/forgot_password
REVIEW_REQUEST_URL=CHANGE_ME/admin_panel
ADMIN_URL=CHANGE_ME/admin

# --- Branding ----------------------------------------------------------------
SITE_TITLE=IDPortal
LOGO=portal_logo.png
COMPANY_NAME=CHANGE_ME
COMPANY_ADDRESS=CHANGE_ME
COMPANY_STATE_ZIP=CHANGE_ME
COMPANY_PHONE=CHANGE_ME
COMPANY_CURRENT_YEAR=$year
COMPANY_EMAIL_SIGNATURE=CHANGE_ME

# --- Email (SMTP) ------------------------------------------------------------
# For an unauthenticated internal relay (port 25): leave MAIL_USE_TLS=false
#   and comment out MAIL_USERNAME / MAIL_PASSWORD.
# For authenticated SMTP (port 587 STARTTLS): set MAIL_USE_TLS=true
#   and fill in MAIL_USERNAME / MAIL_PASSWORD.
MAIL_SERVER=CHANGE_ME
MAIL_PORT=25
MAIL_USE_TLS=false
MAIL_USE_SSL=false
#MAIL_USERNAME=CHANGE_ME
#MAIL_PASSWORD=CHANGE_ME
MAIL_FROM_NAME=IDPortal
MAIL_FROM_ADDRESS=CHANGE_ME
MAIL_DEFAULT_RECIP=CHANGE_ME

# --- Microsoft Entra OAuth (optional) ----------------------------------------
# Leave blank to disable the "Sign in with Microsoft" button.
ENTRA_CLIENT_ID=
ENTRA_CLIENT_SECRET=
ENTRA_TENANT_ID=

# --- Authentication modes ----------------------------------------------------
ADMIN_AUTH_MODE=local
USER_AUTH_MODE=ldap
"@ | Set-Content $EnvFile -Encoding UTF8

        Write-Ok "$EnvFile created with generated secrets"
        Write-Host ""
        Write-Host "Next steps:" -ForegroundColor White
        Write-Host "  1. Edit $EnvFile and replace every CHANGE_ME value"
        Write-Host "  2. Place your SSL certificate at:"
        Write-Host "       $CertsDir\cert.pem"
        Write-Host "       $CertsDir\key.pem"
        Write-Host "  3. Re-run: .\deploy.ps1"
        Write-Host ""
        exit 0
    }
}

# ─── SSL certificates ─────────────────────────────────────────────────────────
function New-SelfSignedPemCert {
    $hostIp = $null
    try {
        $hostIp = (Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue |
                   Where-Object { $_.IPAddress -ne '127.0.0.1' -and $_.PrefixOrigin -ne 'WellKnown' } |
                   Select-Object -First 1).IPAddress
    } catch {}

    $san = "DNS:localhost,IP:127.0.0.1"
    if ($hostIp -and $hostIp -ne '127.0.0.1') { $san += ",IP:$hostIp" }

    $sslConf = [System.IO.Path]::GetTempFileName() + ".cfg"
    @"
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
subjectAltName      = $san
keyUsage            = digitalSignature, keyEncipherment
extendedKeyUsage    = serverAuth
"@ | Set-Content $sslConf -Encoding ASCII

    & $script:OpenSSL req -x509 -nodes -days 365 -newkey rsa:2048 `
        -keyout "$CertsDir\key.pem" `
        -out    "$CertsDir\cert.pem" `
        -config $sslConf 2>&1 | Out-Null

    Remove-Item $sslConf -ErrorAction SilentlyContinue
}

function Setup-Certs {
    Write-Step "SSL certificates"
    New-Item -ItemType Directory -Force -Path $CertsDir | Out-Null

    if ((Test-Path "$CertsDir\cert.pem") -and (Test-Path "$CertsDir\key.pem")) {
        Write-Ok "Certificates found"
        try {
            $certOut = & $script:OpenSSL x509 -enddate -noout -in "$CertsDir\cert.pem" 2>$null
            if ($certOut -match "notAfter=(.+)") {
                $expiry   = [datetime]::Parse($Matches[1].Trim())
                $daysLeft = [int](($expiry - (Get-Date)).TotalDays)
                if ($daysLeft -le 30) {
                    Write-Warn "Certificate expires in $daysLeft days — renew before it lapses"
                } else {
                    Write-Ok "Certificate valid for $daysLeft more days"
                }
            }
        } catch {}
        return
    }

    if ($Test) {
        Write-Info "Test mode: auto-generating self-signed certificate..."
        New-SelfSignedPemCert
        Write-Ok "Self-signed certificate generated (365 days)"
        return
    }

    Write-Host ""
    Write-Host "  No SSL certificate found in $CertsDir\" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "  For production: place your CA-signed cert and key here:"
    Write-Host "    $CertsDir\cert.pem"
    Write-Host "    $CertsDir\key.pem"
    Write-Host ""
    Write-Host "  For testing only: generate a self-signed certificate"
    Write-Host "  (browsers will show a security warning — not suitable for production)"
    Write-Host ""
    $choice = Read-Host "  Generate self-signed cert for testing? [y/N]"
    if ($choice -match "^[Yy]") {
        New-SelfSignedPemCert
        Write-Ok "Self-signed certificate generated (365 days)"
        Write-Warn "Replace with a CA-signed cert before going live"
    } else {
        Die "Place cert.pem and key.pem in $CertsDir\ then re-run."
    }
}

# ─── Git update check ─────────────────────────────────────────────────────────
function Check-GitStatus {
    if (-not (Get-Command git -ErrorAction SilentlyContinue)) { return }
    if (-not (Test-Path ".git")) { return }
    try {
        git fetch origin --quiet 2>&1 | Out-Null
        $behind = git rev-list "HEAD..@{upstream}" --count 2>$null
        if ([int]$behind -gt 0) {
            Write-Host ""
            Write-Warn "$behind commit(s) on origin haven't been pulled yet."
            Write-Warn "Running 'git pull' before deploying ensures you ship the latest changes."
            Write-Host ""
            $confirm = Read-Host "  Pull latest changes now? [Y/n]"
            if ($confirm -notmatch "^[Nn]") {
                git pull
                Write-Ok "Up to date"
            } else {
                Write-Warn "Continuing without pulling — make sure this is intentional"
            }
        } else {
            Write-Ok "Already up to date with origin"
        }
    } catch {}
}

# ─── Database backup ──────────────────────────────────────────────────────────
function Backup-Db {
    $running = docker ps --format '{{.Names}}' 2>$null | Where-Object { $_ -eq $CtrDb }
    if (-not $running) { return }

    Write-Step "Database backup"
    $backupDir = "backups"
    New-Item -ItemType Directory -Force -Path $backupDir | Out-Null

    $timestamp  = Get-Date -Format "yyyyMMdd_HHmmss"
    $sqlFile    = "$backupDir\idportal_${timestamp}.sql"
    $zipFile    = "$backupDir\idportal_${timestamp}.zip"
    $dbUser     = Get-EnvValue "POSTGRES_USER"
    $dbName     = Get-EnvValue "POSTGRES_DB"

    Write-Info "Dumping database to $zipFile..."
    try {
        docker exec $CtrDb pg_dump -U $dbUser $dbName 2>$null | Set-Content $sqlFile -Encoding UTF8
        Compress-Archive -Path $sqlFile -DestinationPath $zipFile -Force
        Remove-Item $sqlFile -ErrorAction SilentlyContinue
        Write-Ok "Backup saved: $zipFile"
    } catch {
        Remove-Item $sqlFile, $zipFile -ErrorAction SilentlyContinue
        Write-Host ""
        Write-Warn "Database backup FAILED before deployment."
        Write-Warn "Deploying without a backup means you cannot roll back if something goes wrong."
        Write-Host ""
        $confirm = Read-Host "  Continue without a backup? [y/N]"
        if ($confirm -notmatch "^[Yy]") { Die "Aborted. Investigate backup failure and retry." }
        Write-Warn "Continuing without backup — you have been warned"
    }

    # Retain only the 10 most recent backups
    Get-ChildItem "$backupDir\idportal_*.zip" |
        Sort-Object LastWriteTime -Descending |
        Select-Object -Skip 10 |
        Remove-Item -ErrorAction SilentlyContinue
}

# ─── Build and deploy ─────────────────────────────────────────────────────────
function Build-Images {
    Write-Step "Building images"
    Write-Info "Running docker compose build..."
    if ($BuildArgs) {
        docker compose -f $ComposeFile build --pull $BuildArgs
    } else {
        docker compose -f $ComposeFile build --pull
    }
    Write-Ok "Images built"
}

function Deploy {
    Write-Step "Deploying containers"
    docker compose -f $ComposeFile up -d --remove-orphans
    Write-Ok "Containers started"
}

# ─── Health check ─────────────────────────────────────────────────────────────
function Wait-Healthy($container, $timeoutSec = 90) {
    $hasHealth = docker inspect --format='{{if .State.Health}}yes{{end}}' $container 2>$null
    if (-not $hasHealth) {
        $state = docker inspect --format='{{.State.Status}}' $container 2>$null
        if ($state -eq "running") { Write-Ok "$container is running"; return }
        Die "$container is not running (state: $state)"
    }

    Write-Info "Waiting for $container to be healthy (timeout: ${timeoutSec}s)..."
    $elapsed = 0
    while ($true) {
        $status = docker inspect --format='{{.State.Health.Status}}' $container 2>$null
        switch ($status) {
            "healthy" {
                Write-Host ""
                Write-Ok "$container is healthy"
                return
            }
            "unhealthy" {
                Write-Host ""
                Write-Err "$container failed its health check"
                docker logs --tail 20 $container
                Die "Deployment aborted. Run 'docker logs $container' for details."
            }
        }
        if ($elapsed -ge $timeoutSec) {
            Write-Host ""
            Write-Err "$container did not become healthy within ${timeoutSec}s"
            docker logs --tail 20 $container
            Die "Deployment timed out."
        }
        Start-Sleep 3
        $elapsed += 3
        Write-Host "  $status (${elapsed}s)...`r" -NoNewline
    }
}

# ─── Post-deploy verification ─────────────────────────────────────────────────
function Verify-Deployment {
    Write-Step "Verifying deployment"
    $allOk = $true
    foreach ($ctr in @($CtrFlask, $CtrDb, $CtrNginx)) {
        $state = docker inspect --format='{{.State.Status}}' $ctr 2>$null
        if ($state -eq "running") {
            Write-Ok "${ctr}: running"
        } else {
            Write-Err "${ctr}: $state"
            $allOk = $false
        }
    }
    if (-not $allOk) {
        Die "One or more containers are not running. Run: docker compose -f $ComposeFile logs"
    }
}

# ─── First admin bootstrap ────────────────────────────────────────────────────
function Bootstrap-FirstAdmin {
    $dbUser = Get-EnvValue "POSTGRES_USER"
    $dbName = Get-EnvValue "POSTGRES_DB"

    $count = docker exec $CtrDb psql -U $dbUser -d $dbName -tAc "SELECT COUNT(*) FROM admins;" 2>$null
    if ($count.Trim() -ne "0") {
        Write-Ok "Admin accounts already exist — skipping bootstrap"
        return
    }

    Write-Step "First admin account setup"
    if ($Test) {
        $fn = "Test"; $ln = "Admin"; $un = "testadmin"; $em = "admin@test.local"
        Write-Host "  Test mode: creating default super admin (testadmin / admin@test.local)"
        Write-Host ""
    } else {
        Write-Host "  No admin accounts found. Set up your first super admin now."
        Write-Host ""
        $fn = Read-Host "  First name"
        $ln = Read-Host "  Last name"
        $un = Read-Host "  Username"
        $em = Read-Host "  Email"
        Write-Host ""
    }

    # Run the credential generation inside the Flask container so bcrypt is available
    $pyScript = @'
import bcrypt, secrets, hashlib, uuid
pw = secrets.token_urlsafe(32).encode()
hashed = bcrypt.hashpw(pw, bcrypt.gensalt()).decode()
token = uuid.uuid4().hex
token_hash = hashlib.sha256(token.encode()).hexdigest()
print(hashed + "|" + token + "|" + token_hash)
'@
    $creds = $pyScript | docker exec -i $CtrFlask python3 -
    $parts     = $creds.Trim() -split '\|'
    $hashedPw  = $parts[0]
    $token     = $parts[1]
    $tokenHash = $parts[2]

    # Escape single quotes for SQL
    $fnE = $fn -replace "'", "''"
    $lnE = $ln -replace "'", "''"
    $unE = $un -replace "'", "''"
    $emE = $em -replace "'", "''"
    $pwE = $hashedPw -replace "'", "''"

    $userId = docker exec $CtrDb psql -U $dbUser -d $dbName -tAc `
        "INSERT INTO admins (first_name, last_name, username, email, role, password) VALUES ('$fnE', '$lnE', '$unE', '$emE', 'super', '$pwE') RETURNING id;"
    $userId = $userId.Trim()

    docker exec $CtrDb psql -U $dbUser -d $dbName -c `
        "INSERT INTO admin_forgot_password (user_id, token, expire_after) VALUES ($userId, '$tokenHash', now() + interval '24 hours');" | Out-Null

    $forgotUrl = Get-EnvValue "FORGOT_PASSWORD_URL"
    Write-Ok "Super admin '$un' created"
    Write-Host ""
    Write-Host "  Set your password using this link (expires in 24 hours):" -ForegroundColor Yellow
    Write-Host "  ${forgotUrl}?token=${token}" -ForegroundColor Cyan
    Write-Host ""
    Write-Warn "Save this link — it will not be shown again."
}

# ─── Nginx test config ────────────────────────────────────────────────────────
function Setup-NginxTestConfig {
    if (-not $Test) { return }
    $httpsPort = Get-EnvValue "HTTPS_PORT"
    if (-not $httpsPort) { $httpsPort = "8443" }
    $conf = Get-Content "docker\nginx\nginx.ssl.conf" -Raw
    $conf = $conf -replace 'return 301 https://\$host\$request_uri', "return 301 https://`$host:${httpsPort}`$request_uri"
    Set-Content "docker\nginx\nginx.test.conf" $conf -Encoding UTF8
}

function Sync-TestUrls {
    if (-not $Test) { return }
    $port = Get-EnvValue "HTTPS_PORT"
    if (-not $port) { $port = "8443" }
    $content = Get-Content $EnvFile
    $content = $content -replace 'USER_LOGIN_URL=https://localhost:\d+$',              "USER_LOGIN_URL=https://localhost:$port"
    $content = $content -replace 'FORGOT_PASSWORD_URL=https://localhost:\d+/forgot_password', "FORGOT_PASSWORD_URL=https://localhost:$port/forgot_password"
    $content = $content -replace 'REVIEW_REQUEST_URL=https://localhost:\d+/admin_panel',      "REVIEW_REQUEST_URL=https://localhost:$port/admin_panel"
    $content = $content -replace 'ADMIN_URL=https://localhost:\d+/admin',              "ADMIN_URL=https://localhost:$port/admin"
    Set-Content $EnvFile $content -Encoding UTF8
}

# ─── Summary ──────────────────────────────────────────────────────────────────
function Print-Summary {
    $cfFlag = if ($Test) { "-f $ComposeFile " } else { "" }
    Write-Host ""
    Write-Host "╔══════════════════════════════════╗" -ForegroundColor Green
    Write-Host "║     Deployment complete!         ║" -ForegroundColor Green
    Write-Host "╚══════════════════════════════════╝" -ForegroundColor Green
    Write-Host ""
    if ($Test) {
        $httpsPort   = Get-EnvValue "HTTPS_PORT";   if (-not $httpsPort)   { $httpsPort   = "8443" }
        $httpPort    = Get-EnvValue "HTTP_PORT";    if (-not $httpPort)    { $httpPort    = "8080" }
        $mailhogPort = Get-EnvValue "MAILHOG_PORT"; if (-not $mailhogPort) { $mailhogPort = "8025" }
        Write-Host "  Portal  : " -NoNewline
        Write-Host "https://localhost:$httpsPort" -ForegroundColor Cyan -NoNewline
        Write-Host "  (accept the self-signed cert warning)"
        Write-Host "  Admin   : " -NoNewline; Write-Host "https://localhost:$httpsPort/admin" -ForegroundColor Cyan
        Write-Host "  MailHog : " -NoNewline; Write-Host "http://localhost:$mailhogPort" -ForegroundColor Cyan
        Write-Host "  HTTP    : http://localhost:$httpPort  ->  redirects to $httpsPort"
        Write-Host ""
        Write-Host "  Test LDAP login: testuser@dev.local / TestPass123!"
    } else {
        $siteUrl  = Get-EnvValue "USER_LOGIN_URL"
        $adminUrl = Get-EnvValue "ADMIN_URL"
        Write-Host "  Portal : " -NoNewline; Write-Host $siteUrl  -ForegroundColor Cyan
        Write-Host "  Admin  : " -NoNewline; Write-Host $adminUrl -ForegroundColor Cyan
    }
    Write-Host ""
    Write-Host "  Useful commands:"
    Write-Host "    docker compose ${cfFlag}logs -f              # stream all logs"
    Write-Host "    docker compose ${cfFlag}logs -f $CtrFlask  # stream app logs"
    Write-Host "    docker compose ${cfFlag}ps                   # container status"
    Write-Host "    docker compose ${cfFlag}down                 # stop everything"
    Write-Host "    .\deploy.ps1 -Update                        # upgrade to latest version"
    Write-Host ""
}

# ─── Main ─────────────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "╔══════════════════════════════════╗" -ForegroundColor White
Write-Host "║      IDPortal  ·  Deploy         ║" -ForegroundColor White
Write-Host "╚══════════════════════════════════╝" -ForegroundColor White
Write-Host ""

Check-Prerequisites

if ($Mode -eq "auto") {
    $Mode = if (Test-Path $EnvFile) { "update" } else { "fresh" }
}
Write-Info "Mode: $Mode"

if ($Mode -eq "fresh") {
    Setup-Env
    Sync-TestUrls
    Validate-Env
    Setup-Certs
} else {
    Check-GitStatus
    Sync-TestUrls
    Validate-Env
    Setup-Certs
    Backup-Db
}

Setup-NginxTestConfig
Build-Images
Deploy

Wait-Healthy $CtrDb    90
Wait-Healthy $CtrFlask 90
Wait-Healthy $CtrNginx 30

Verify-Deployment
Bootstrap-FirstAdmin
Print-Summary
