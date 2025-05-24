from flask import Flask
from dotenv import load_dotenv
from extensions import mail

def create_app():
    app = Flask(__name__, instance_relative_config=True)
    load_dotenv()
    env = app.config.get('ENV', 'production').title()
    app.config.from_object(f'config.{env}Config')
    app.config.from_pyfile('config.py', silent=True)
    app.config.update(
        MAIL_SERVER = app.config["MAIL_SERVER"],
        MAIL_PORT = app.config["MAIL_PORT"],
        MAIL_USE_TLS = app.config["MAIL_USE_TLS"],
        MAIL_USERNAME = app.config["MAIL_USERNAME"],
        MAIL_PASSWORD = app.config["MAIL_PWD"],
        MAIL_DEFAULT_SENDER = (app.config["MAIL_DEFAULT_SENDER"], 
                               app.config["MAIL_USERNAME"]
        )
    )

    mail.init_app(app)

    from routes import blueprint
    app.register_blueprint(blueprint=blueprint)

    @app.context_processor
    def inject():
        return {
            "SITE_TITLE" : app.config["SITE_TITLE"],
            "LOGO"       : app.config["LOGO"]
            }
    
    return app

app = create_app()

if __name__ == '__main__':
    app.run(debug=True, threaded=True)