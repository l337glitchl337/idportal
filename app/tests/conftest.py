import os
import pytest
from unittest.mock import MagicMock
from flask import Flask
from routes import admin_blueprint, user_blueprint, auth_blueprint
from helpers import generate_csrf_token


def make_app(**overrides):
    """Minimal Flask app with mocked services for testing."""
    app = Flask(
        __name__,
        template_folder=os.path.join(os.path.dirname(__file__), '..', 'templates'),
    )
    app.config.update({
        'TESTING': True,
        'SECRET_KEY': 'test-secret-key-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx',
        'SESSION_COOKIE_SECURE': False,
        'UPLOAD_FOLDER': '/tmp/test-uploads',
        'ADMIN_AUTH_MODE': 'local',
        'USER_AUTH_MODE': 'ldap',
        'ENTRA_CLIENT_ID': None,
        'ENTRA_CLIENT_SECRET': None,
        'ENTRA_TENANT_ID': '',
        'FORGOT_PASSWORD_URL': 'https://test.example.com/forgot_password',
        'SITE_TITLE': 'Test IDPortal',
        'LOGO': None,
        'COMPANY_NAME': 'Test Co',
        'COMPANY_ADDRESS': '123 Test St',
        'COMPANY_STATE_ZIP': 'Test, TS 00000',
        'COMPANY_PHONE': '555-0000',
        'COMPANY_CURRENT_YEAR': '2026',
        'COMPANY_EMAIL_SIGNATURE': 'Test IT',
        'REVIEW_REQUEST_URL': 'https://test.example.com/admin_panel',
        'USER_LOGIN_URL': 'https://test.example.com/login',
        'ADMIN_URL': 'https://test.example.com/admin',
        **overrides,
    })

    app.register_blueprint(admin_blueprint, url_prefix='/')
    app.register_blueprint(user_blueprint, url_prefix='/')
    app.register_blueprint(auth_blueprint, url_prefix='/')

    app.db = MagicMock()
    app.auth_service = MagicMock()
    app.admin_service = MagicMock()
    app.ldap_service = MagicMock()
    app.email_service = MagicMock()
    app.submission_service = MagicMock()

    @app.context_processor
    def _inject_csrf():
        return {'csrf_token': generate_csrf_token}

    @app.context_processor
    def _inject_globals():
        return {
            'entra_enabled': bool(app.config.get('ENTRA_CLIENT_ID')),
            'admin_auth_mode': app.config['ADMIN_AUTH_MODE'],
            'user_auth_mode': app.config['USER_AUTH_MODE'],
            'SITE_TITLE': app.config.get('SITE_TITLE'),
            'LOGO': app.config.get('LOGO'),
            'COMPANY_NAME': app.config.get('COMPANY_NAME'),
            'COMPANY_ADDRESS': app.config.get('COMPANY_ADDRESS'),
            'COMPANY_STATE_ZIP': app.config.get('COMPANY_STATE_ZIP'),
            'COMPANY_PHONE': app.config.get('COMPANY_PHONE'),
            'COMPANY_CURRENT_YEAR': app.config.get('COMPANY_CURRENT_YEAR'),
            'COMPANY_EMAIL_SIGNATURE': app.config.get('COMPANY_EMAIL_SIGNATURE'),
            'FORGOT_PASSWORD_URL': app.config.get('FORGOT_PASSWORD_URL'),
            'REVIEW_REQUEST_URL': app.config.get('REVIEW_REQUEST_URL'),
            'USER_LOGIN_URL': app.config.get('USER_LOGIN_URL'),
        }

    os.makedirs('/tmp/test-uploads', exist_ok=True)
    return app


@pytest.fixture
def app():
    return make_app()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def admin_client(app):
    c = app.test_client()
    with c.session_transaction() as sess:
        sess['admin_username'] = 'testadmin'
        sess['first_name'] = 'Test'
        sess['last_name'] = 'Admin'
        sess['email'] = 'testadmin@example.com'
        sess['role'] = 'super'
        sess['on_login'] = 0
        sess['user_id'] = 1
    return c


@pytest.fixture
def manager_client(app):
    c = app.test_client()
    with c.session_transaction() as sess:
        sess['admin_username'] = 'mgr'
        sess['first_name'] = 'Manager'
        sess['last_name'] = 'User'
        sess['email'] = 'mgr@example.com'
        sess['role'] = 'manager'
        sess['on_login'] = 0
        sess['user_id'] = 2
    return c


@pytest.fixture
def user_client(app):
    c = app.test_client()
    with c.session_transaction() as sess:
        sess['user_logged_in'] = True
        sess['attrs'] = {
            'First Name': 'Test',
            'Last Name': 'User',
            'Email': 'user@example.com',
            'ID Number': '12345',
            'Location': 'HQ',
            'cn': 'user@example.com',
        }
        for k, v in sess['attrs'].items():
            sess[k] = v
    return c
