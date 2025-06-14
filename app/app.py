from flask import Flask
from dotenv import load_dotenv
from services import Database, AdminService, EmailService, LDAPService, SubmissionService, AuthService
from routes import admin_blueprint, user_blueprint

def create_app():
    app = Flask(__name__, instance_relative_config=True)
    load_dotenv()
    env = app.config.get('ENV', 'production').title()
    app.config.from_object(f'config.{env}Config')
    app.config.from_pyfile('config.py', silent=True)
    app.config["UPLOAD_FOLDER"] = "static/uploads"
    app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024
    app.register_blueprint(admin_blueprint, url_prefix="/")
    app.register_blueprint(user_blueprint, url_prefix="/")

    @app.context_processor
    def inject():
        return {
            "SITE_TITLE" : app.config["SITE_TITLE"],
            "LOGO"       : app.config["LOGO"],
            "COMPANY_NAME" : app.config["COMPANY_NAME"],
            "COMPANY_ADDRESS" : app.config["COMPANY_ADDRESS"],
            "COMPANY_STATE_ZIP" : app.config["COMPANY_STATE_ZIP"],
            "COMPANY_PHONE" : app.config["COMPANY_PHONE"],
            "COMPANY_CURRENT_YEAR" : app.config["COMPANY_CURRENT_YEAR"],
            "COMPANY_EMAIL_SIGNATURE" : app.config["COMPANY_EMAIL_SIGNATURE"],
            "FORGOT_PASSWORD_URL" : app.config["FORGOT_PASSWORD_URL"],
            "REVIEW_REQUEST_URL" : app.config["REVIEW_REQUEST_URL"],
            "USER_LOGIN_URL" : app.config["USER_LOGIN_URL"]
        }
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