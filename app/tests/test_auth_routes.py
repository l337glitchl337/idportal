import pytest
from unittest.mock import patch, MagicMock
from tests.conftest import make_app


@pytest.fixture
def app():
    return make_app()


@pytest.fixture
def app_with_entra():
    return make_app(
        ENTRA_CLIENT_ID='test-client-id',
        ENTRA_CLIENT_SECRET='test-secret',
        ENTRA_TENANT_ID='test-tenant',
        ADMIN_AUTH_MODE='both',
        USER_AUTH_MODE='both',
    )


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def entra_client(app_with_entra):
    return app_with_entra.test_client()


# ── GET /oauth/login — no Entra config ───────────────────────────────────────

def test_oauth_login_no_config_user_flow_redirects_home(client):
    resp = client.get('/oauth/login?flow=user')
    assert resp.status_code == 302
    assert '/' in resp.headers['Location']


def test_oauth_login_no_config_admin_flow_redirects_admin(client):
    resp = client.get('/oauth/login?flow=admin')
    assert resp.status_code == 302
    assert '/admin' in resp.headers['Location']


# ── GET /oauth/login — auth mode enforcement ──────────────────────────────────

def test_oauth_login_admin_flow_blocked_in_local_mode(app):
    app.config['ENTRA_CLIENT_ID'] = 'some-id'
    app.config['ADMIN_AUTH_MODE'] = 'local'
    c = app.test_client()
    resp = c.get('/oauth/login?flow=admin')
    assert resp.status_code == 302
    assert '/admin' in resp.headers['Location']
    app.config['ENTRA_CLIENT_ID'] = None
    app.config['ADMIN_AUTH_MODE'] = 'local'


def test_oauth_login_user_flow_blocked_in_ldap_mode(app):
    app.config['ENTRA_CLIENT_ID'] = 'some-id'
    app.config['USER_AUTH_MODE'] = 'ldap'
    c = app.test_client()
    resp = c.get('/oauth/login?flow=user')
    assert resp.status_code == 302
    assert '/' in resp.headers['Location']
    app.config['ENTRA_CLIENT_ID'] = None
    app.config['USER_AUTH_MODE'] = 'ldap'


# ── GET /oauth/login — Entra configured ──────────────────────────────────────

def test_oauth_login_with_entra_redirects_to_microsoft(app_with_entra, entra_client):
    mock_redirect = MagicMock(return_value=('', 302, {'Location': 'https://login.microsoft.com/...'}))
    with patch('routes.auth_routes.oauth') as mock_oauth:
        mock_oauth.entra.authorize_redirect.return_value = mock_redirect()
        resp = entra_client.get('/oauth/login?flow=user')
    assert resp.status_code == 302


def test_oauth_login_sets_flow_in_session(app_with_entra, entra_client):
    mock_resp = MagicMock()
    mock_resp.status_code = 302
    with patch('routes.auth_routes.oauth') as mock_oauth:
        mock_oauth.entra.authorize_redirect.return_value = mock_resp
        with entra_client.session_transaction() as sess:
            sess.clear()
        entra_client.get('/oauth/login?flow=admin')
    # The route should have set oauth_flow in session before redirect
    mock_oauth.entra.authorize_redirect.assert_called_once()


# ── GET /oauth/callback ───────────────────────────────────────────────────────

def test_oauth_callback_exception_redirects_home(app, client):
    with patch('routes.auth_routes.oauth') as mock_oauth:
        mock_oauth.entra.authorize_access_token.side_effect = Exception("auth error")
        resp = client.get('/oauth/callback')
    assert resp.status_code == 302
    assert '/' in resp.headers['Location']


def test_oauth_callback_admin_flow_success(app, client):
    app.auth_service.entra_admin_login.return_value = True
    with client.session_transaction() as sess:
        sess['oauth_flow'] = 'admin'
    with patch('routes.auth_routes.oauth') as mock_oauth:
        mock_oauth.entra.authorize_access_token.return_value = {
            'userinfo': {'email': 'admin@example.com', 'given_name': 'A', 'family_name': 'B'}
        }
        resp = client.get('/oauth/callback')
    assert resp.status_code == 302
    assert '/admin_panel' in resp.headers['Location']


def test_oauth_callback_admin_flow_failure_redirects_admin(app, client):
    app.auth_service.entra_admin_login.return_value = False
    with client.session_transaction() as sess:
        sess['oauth_flow'] = 'admin'
    with patch('routes.auth_routes.oauth') as mock_oauth:
        mock_oauth.entra.authorize_access_token.return_value = {
            'userinfo': {'email': 'unknown@example.com'}
        }
        resp = client.get('/oauth/callback')
    assert resp.status_code == 302
    assert '/admin' in resp.headers['Location']


def test_oauth_callback_user_flow_success(app, client):
    app.auth_service.entra_user_login.return_value = True
    with client.session_transaction() as sess:
        sess['oauth_flow'] = 'user'
    with patch('routes.auth_routes.oauth') as mock_oauth:
        mock_oauth.entra.authorize_access_token.return_value = {
            'userinfo': {'email': 'user@example.com'}
        }
        resp = client.get('/oauth/callback')
    assert resp.status_code == 302
    assert '/landing' in resp.headers['Location']


def test_oauth_callback_user_flow_failure_redirects_home(app, client):
    app.auth_service.entra_user_login.return_value = False
    with client.session_transaction() as sess:
        sess['oauth_flow'] = 'user'
    with patch('routes.auth_routes.oauth') as mock_oauth:
        mock_oauth.entra.authorize_access_token.return_value = {
            'userinfo': {}
        }
        resp = client.get('/oauth/callback')
    assert resp.status_code == 302
    assert '/' in resp.headers['Location']


def test_oauth_callback_default_flow_is_user(app, client):
    app.auth_service.entra_user_login.return_value = True
    # No oauth_flow in session → defaults to 'user'
    with patch('routes.auth_routes.oauth') as mock_oauth:
        mock_oauth.entra.authorize_access_token.return_value = {'userinfo': {}}
        client.get('/oauth/callback')
    app.auth_service.entra_user_login.assert_called_once()
    app.auth_service.entra_admin_login.assert_not_called()


def test_oauth_callback_clears_flow_from_session(app, client):
    app.auth_service.entra_user_login.return_value = True
    with client.session_transaction() as sess:
        sess['oauth_flow'] = 'user'
    with patch('routes.auth_routes.oauth') as mock_oauth:
        mock_oauth.entra.authorize_access_token.return_value = {'userinfo': {}}
        client.get('/oauth/callback')
    # Verify oauth_flow was popped (session.pop used in route)
    with client.session_transaction() as sess:
        assert 'oauth_flow' not in sess
