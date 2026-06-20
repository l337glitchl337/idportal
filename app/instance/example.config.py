# IDPortal instance config — copy this file to instance/config.py to apply overrides.
#
# Flask loads instance/config.py AFTER app.py sets its defaults, so any key set
# here takes precedence. This is the right place for environment-specific tweaks
# that don't belong in .env (which is the source of truth for all other config).
#
# All application config (LDAP, email, branding, URLs, database) belongs in .env.
# Only use this file for Flask-level overrides like the examples below.

# ─── Development / HTTP-only overrides ───────────────────────────────────────
# Uncomment when running the app over plain HTTP (no SSL) in a dev environment.
# Never set these in production.
#
# DEBUG = True
# SESSION_COOKIE_SECURE = False

# ─── LDAP TLS notes ──────────────────────────────────────────────────────────
# Two secure LDAP options are supported:
#
#   STARTTLS  — set LDAP_USE_TLS=true in .env (upgrades an ldap:// connection)
#               If your LDAP server uses a private/internal CA, also set:
#               LDAP_TLS_CACERTFILE=/path/to/ca.pem  (inside the container)
#
#   LDAPS     — set LDAP_URI=ldaps://host:636 and LDAP_USE_TLS=false in .env
#               LDAPS encrypts from the start and avoids STARTTLS negotiation.
#               Recommended when your AD/LDAP server supports port 636.
