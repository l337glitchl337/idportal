from flask import Flask
from dotenv import load_dotenv
from datetime import timedelta
from services import Database, AdminService, EmailService, LDAPService, SubmissionService, AuthService
from routes import admin_blueprint, user_blueprint
from helpers import generate_csrf_token, validate_csrf
import os

_REQUIRED_CONFIG = [
    "SECRET_KEY",
    "POSTGRES_DB", "POSTGRES_USER", "POSTGRES_PASSWORD", "POSTGRES_HOST", "POSTGRES_PORT",
    "LDAP_URI", "LDAP_BIND_DN", "LDAP_BIND_PWD", "LDAP_SEARCH_BASE",
    "LDAP_SEARCH_FILTER", "LDAP_USE_TLS",
    "MAIL_SERVER", "MAIL_PORT", "MAIL_DEFAULT_SENDER",
    "FORGOT_PASSWORD_URL", "SITE_TITLE",
]

def _validate_config(app):
    missing = [k for k in _REQUIRED_CONFIG if not app.config.get(k)]
    if missing:
        raise RuntimeError(f"Missing required configuration variables: {', '.join(missing)}")

def create_app():
    app = Flask(__name__, instance_relative_config=True)
    load_dotenv()

    # ── Flask core ────────────────────────────────────────────────────────────
    app.config["SECRET_KEY"]         = os.environ.get("SECRET_KEY")
    app.config["MAX_CONTENT_LENGTH"] = 20 * 1024 * 1024
    app.config["UPLOAD_FOLDER"]      = "/app/uploads"

    # ── Session security (production-safe — overridden by instance config in dev)
    app.config["SESSION_COOKIE_HTTPONLY"]    = True
    app.config["SESSION_COOKIE_SAMESITE"]    = "Lax"
    app.config["SESSION_COOKIE_SECURE"]      = True
    app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(hours=8)

    # ── PostgreSQL ────────────────────────────────────────────────────────────
    app.config["POSTGRES_DB"]       = os.environ.get("POSTGRES_DBNAME")
    app.config["POSTGRES_USER"]     = os.environ.get("POSTGRES_USER")
    app.config["POSTGRES_PASSWORD"] = os.environ.get("POSTGRES_PASSWORD")
    app.config["POSTGRES_HOST"]     = os.environ.get("POSTGRES_HOST")
    app.config["POSTGRES_PORT"]     = os.environ.get("POSTGRES_PORT")

    # ── LDAP ─────────────────────────────────────────────────────────────────
    app.config["LDAP_URI"]           = os.environ.get("LDAP_URI")
    app.config["LDAP_BIND_DN"]       = os.environ.get("LDAP_BIND_DN")
    app.config["LDAP_BIND_PWD"]      = os.environ.get("LDAP_BIND_PWD")
    app.config["LDAP_SEARCH_BASE"]   = os.environ.get("LDAP_SEARCH_BASE")
    app.config["LDAP_SEARCH_FILTER"] = os.environ.get("LDAP_SEARCH_FILTER")
    app.config["LDAP_ATTRIBUTES"]    = os.environ.get("LDAP_ATTRIBUTES", "{}")
    app.config["LDAP_USE_TLS"]       = os.environ.get("LDAP_USE_TLS")

    # ── Email ─────────────────────────────────────────────────────────────────
    app.config["MAIL_SERVER"]         = os.environ.get("MAIL_SERVER")
    app.config["MAIL_PORT"]           = os.environ.get("MAIL_PORT")
    app.config["MAIL_DEFAULT_SENDER"] = (os.environ.get("MAIL_FROM_NAME"), os.environ.get("MAIL_FROM_ADDRESS"))
    app.config["MAIL_DEFAULT_RECIP"]  = os.environ.get("MAIL_DEFAULT_RECIP")

    # ── Branding ──────────────────────────────────────────────────────────────
    app.config["SITE_TITLE"]              = os.environ.get("SITE_TITLE")
    app.config["LOGO"]                    = os.environ.get("LOGO")
    app.config["USER_LOGIN_URL"]          = os.environ.get("USER_LOGIN_URL")
    app.config["FORGOT_PASSWORD_URL"]     = os.environ.get("FORGOT_PASSWORD_URL")
    app.config["REVIEW_REQUEST_URL"]      = os.environ.get("REVIEW_REQUEST_URL")
    app.config["ADMIN_URL"]               = os.environ.get("ADMIN_URL")
    app.config["COMPANY_NAME"]            = os.environ.get("COMPANY_NAME")
    app.config["COMPANY_ADDRESS"]         = os.environ.get("COMPANY_ADDRESS")
    app.config["COMPANY_STATE_ZIP"]       = os.environ.get("COMPANY_STATE_ZIP")
    app.config["COMPANY_PHONE"]           = os.environ.get("COMPANY_PHONE")
    app.config["COMPANY_CURRENT_YEAR"]    = os.environ.get("COMPANY_CURRENT_YEAR")
    app.config["COMPANY_EMAIL_SIGNATURE"] = os.environ.get("COMPANY_EMAIL_SIGNATURE")

    # ── Instance config overrides (dev/instance/config.py in development) ─────
    app.config.from_pyfile("config.py", silent=True)

    _validate_config(app)
    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

    app.register_blueprint(admin_blueprint, url_prefix="/")
    app.register_blueprint(user_blueprint, url_prefix="/")

    @app.context_processor
    def inject():
        return {
            "SITE_TITLE"              : app.config["SITE_TITLE"],
            "LOGO"                    : app.config["LOGO"],
            "COMPANY_NAME"            : app.config["COMPANY_NAME"],
            "COMPANY_ADDRESS"         : app.config["COMPANY_ADDRESS"],
            "COMPANY_STATE_ZIP"       : app.config["COMPANY_STATE_ZIP"],
            "COMPANY_PHONE"           : app.config["COMPANY_PHONE"],
            "COMPANY_CURRENT_YEAR"    : app.config["COMPANY_CURRENT_YEAR"],
            "COMPANY_EMAIL_SIGNATURE" : app.config["COMPANY_EMAIL_SIGNATURE"],
            "FORGOT_PASSWORD_URL"     : app.config["FORGOT_PASSWORD_URL"],
            "REVIEW_REQUEST_URL"      : app.config["REVIEW_REQUEST_URL"],
            "USER_LOGIN_URL"          : app.config["USER_LOGIN_URL"],
        }

    app.before_request(validate_csrf)

    @app.context_processor
    def inject_csrf():
        return {"csrf_token": generate_csrf_token}

    app.json.sort_keys = False
    app.db = Database(app)
    app.admin_service = AdminService(app.db)
    app.auth_service = AuthService(app.db)
    app.ldap_service = LDAPService(app.auth_service, app, app.db)
    app.email_service = EmailService(app.db, app)
    app.submission_service = SubmissionService(app.db, app.email_service)
    return app

app = create_app()

if __name__ == '__main__':
    app.run()
