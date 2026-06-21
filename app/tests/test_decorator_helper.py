import pytest
from flask import Flask, session
from helpers.decorator_helper import DecoratorHelper


@pytest.fixture
def app():
    a = Flask(__name__)
    a.config.update({'TESTING': True, 'SECRET_KEY': 'dec-test'})

    # Stub redirect targets used by the decorators
    @a.route('/', endpoint='user.home')
    def user_home():
        return 'home', 200

    @a.route('/admin-login', endpoint='admin.admin')
    def admin_login():
        return 'admin login', 200

    @a.route('/user-only')
    @DecoratorHelper.check_login
    def user_only():
        return 'user ok', 200

    @a.route('/admin-only')
    @DecoratorHelper.check_admin_login
    def admin_only():
        return 'admin ok', 200

    @a.route('/change_admin_password', endpoint='admin.change_admin_password')
    @DecoratorHelper.check_admin_login
    def change_admin_password():
        return 'change pw ok', 200

    @a.route('/first-login-check')
    @DecoratorHelper.check_admin_login
    @DecoratorHelper.check_first_login
    def first_login_check():
        return 'past first login', 200

    return a


@pytest.fixture
def client(app):
    return app.test_client()


# ── check_login ──────────────────────────────────────────────────────────────

def test_check_login_allows_logged_in_user(client):
    with client.session_transaction() as sess:
        sess['user_logged_in'] = True
    assert client.get('/user-only').status_code == 200


def test_check_login_redirects_unauthenticated(client):
    resp = client.get('/user-only')
    assert resp.status_code == 302
    assert '/' in resp.headers['Location']


def test_check_login_false_flag_redirects(client):
    with client.session_transaction() as sess:
        sess['user_logged_in'] = False
    assert client.get('/user-only').status_code == 302


# ── check_admin_login ─────────────────────────────────────────────────────────

def test_check_admin_login_allows_admin(client):
    with client.session_transaction() as sess:
        sess['admin_username'] = 'admin'
    assert client.get('/admin-only').status_code == 200


def test_check_admin_login_redirects_unauthenticated(client):
    resp = client.get('/admin-only')
    assert resp.status_code == 302
    assert '/admin-login' in resp.headers['Location']


def test_check_admin_login_forgot_token_allows_change_password(client):
    with client.session_transaction() as sess:
        sess['forgot_password_token'] = 'reset-token'
        sess['admin_username'] = 'admin'
    assert client.get('/change_admin_password').status_code == 200


def test_check_admin_login_forgot_token_redirects_other_endpoints(client):
    with client.session_transaction() as sess:
        sess['forgot_password_token'] = 'reset-token'
    resp = client.get('/admin-only')
    assert resp.status_code == 302
    assert '/admin-login' in resp.headers['Location']


# ── check_first_login ─────────────────────────────────────────────────────────

def test_check_first_login_allows_when_on_login_zero(client):
    with client.session_transaction() as sess:
        sess['admin_username'] = 'admin'
        sess['on_login'] = 0
    assert client.get('/first-login-check').status_code == 200


def test_check_first_login_redirects_when_on_login_one(client):
    with client.session_transaction() as sess:
        sess['admin_username'] = 'admin'
        sess['on_login'] = 1
    resp = client.get('/first-login-check')
    assert resp.status_code == 302
    assert '/admin-login' in resp.headers['Location']
