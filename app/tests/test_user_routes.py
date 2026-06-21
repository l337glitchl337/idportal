import io
import pytest
from unittest.mock import patch, MagicMock
from tests.conftest import make_app


JPEG_HEADER = b'\xff\xd8\xff' + b'\x00' * 9
PNG_HEADER = b'\x89PNG\r\n\x1a\n' + b'\x00' * 4


@pytest.fixture
def app():
    return make_app()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def user_client(app):
    c = app.test_client()
    with c.session_transaction() as sess:
        sess['user_logged_in'] = True
        attrs = {
            'First Name': 'Alice',
            'Last Name': 'Smith',
            'Email': 'alice@example.com',
            'ID Number': 'EMP001',
            'Location': 'HQ',
            'cn': 'alice@example.com',
        }
        sess['attrs'] = attrs
        for k, v in attrs.items():
            sess[k] = v
    return c


# ── GET / ────────────────────────────────────────────────────────────────────

def test_home_renders_login(client):
    with patch('routes.user_routes.render_template', return_value='') as mock_rt:
        resp = client.get('/')
    assert resp.status_code == 200
    mock_rt.assert_called_once_with('login.html')


# ── POST /login ───────────────────────────────────────────────────────────────

def test_login_blocked_in_entra_mode(app, client):
    app.config['USER_AUTH_MODE'] = 'entra'
    resp = client.post('/login', data={'email': 'u@example.com', 'password': 'pass'})
    assert resp.status_code == 302
    assert '/' in resp.headers['Location']
    app.config['USER_AUTH_MODE'] = 'ldap'


def test_login_success_redirects_to_landing(app, client):
    app.ldap_service.auth_user.return_value = (
        None,
        {'First Name': 'Alice', 'Email': 'alice@example.com', 'cn': 'alice'},
        True,
    )
    app.auth_service.set_session_attrs.return_value = True
    resp = client.post('/login', data={'email': 'alice@example.com', 'password': 'pass'})
    assert resp.status_code == 302
    assert '/landing' in resp.headers['Location']


def test_login_failure_redirects_home(app, client):
    app.ldap_service.auth_user.return_value = (None, {}, False)
    with patch('routes.user_routes.login_limiter') as mock_lim:
        mock_lim.is_allowed.return_value = True
        resp = client.post('/login', data={'email': 'u@example.com', 'password': 'bad'})
    assert resp.status_code == 302
    assert '/' in resp.headers['Location']


def test_login_failure_with_message(app, client):
    app.ldap_service.auth_user.return_value = ("Account locked", {}, False)
    with patch('routes.user_routes.login_limiter') as mock_lim:
        mock_lim.is_allowed.return_value = True
        resp = client.post('/login', data={'email': 'u@example.com', 'password': 'x'})
    assert resp.status_code == 302


def test_login_rate_limited(app, client):
    with patch('routes.user_routes.login_limiter') as mock_lim:
        mock_lim.is_allowed.return_value = False
        resp = client.post('/login', data={'email': 'u@example.com', 'password': 'x'})
    assert resp.status_code == 302
    app.ldap_service.auth_user.assert_not_called()


# ── GET /landing ──────────────────────────────────────────────────────────────

def test_landing_requires_login(client):
    resp = client.get('/landing')
    assert resp.status_code == 302
    assert '/' in resp.headers['Location']


def test_landing_with_session(user_client):
    with patch('routes.user_routes.render_template', return_value=''):
        resp = user_client.get('/landing')
    assert resp.status_code == 200


# ── GET /upload_form ──────────────────────────────────────────────────────────

def test_upload_form_requires_login(client):
    resp = client.get('/upload_form')
    assert resp.status_code == 302


def test_upload_form_with_session(user_client):
    with patch('routes.user_routes.render_template', return_value=''):
        resp = user_client.get('/upload_form')
    assert resp.status_code == 200


# ── POST /upload_photo ────────────────────────────────────────────────────────

def _make_upload(filename, content):
    return (io.BytesIO(content), filename)


def test_upload_photo_requires_login(client):
    resp = client.post('/upload_photo')
    assert resp.status_code == 302


def test_upload_photo_success(app, user_client):
    app.submission_service.create_submission.return_value = True
    resp = user_client.post('/upload_photo', content_type='multipart/form-data', data={
        'photo': _make_upload('photo.jpg', JPEG_HEADER),
        'drivers_license': _make_upload('license.jpg', JPEG_HEADER),
    })
    assert resp.status_code == 302
    app.submission_service.create_submission.assert_called_once()
    app.email_service.send_email_alert.assert_called_once()


def test_upload_photo_invalid_extension(user_client):
    resp = user_client.post('/upload_photo', content_type='multipart/form-data', data={
        'photo': _make_upload('photo.gif', b'GIF89a'),
        'drivers_license': _make_upload('license.jpg', JPEG_HEADER),
    })
    assert resp.status_code == 302


def test_upload_photo_bad_magic_bytes(user_client):
    resp = user_client.post('/upload_photo', content_type='multipart/form-data', data={
        'photo': _make_upload('photo.jpg', b'\x00' * 12),
        'drivers_license': _make_upload('license.jpg', JPEG_HEADER),
    })
    assert resp.status_code == 302


def test_upload_photo_png_accepted(app, user_client):
    app.submission_service.create_submission.return_value = True
    resp = user_client.post('/upload_photo', content_type='multipart/form-data', data={
        'photo': _make_upload('photo.png', PNG_HEADER),
        'drivers_license': _make_upload('license.png', PNG_HEADER),
    })
    assert resp.status_code == 302
    app.submission_service.create_submission.assert_called_once()


def test_upload_photo_submission_failure_cleans_up(app, user_client):
    app.submission_service.create_submission.return_value = False
    with patch('routes.user_routes.os.remove') as mock_rm:
        user_client.post('/upload_photo', content_type='multipart/form-data', data={
            'photo': _make_upload('photo.jpg', JPEG_HEADER),
            'drivers_license': _make_upload('license.jpg', JPEG_HEADER),
        })
    assert mock_rm.call_count == 2


def test_upload_photo_empty_filename_redirects(user_client):
    resp = user_client.post('/upload_photo', content_type='multipart/form-data', data={
        'photo': (io.BytesIO(b''), ''),
        'drivers_license': (io.BytesIO(b''), ''),
    })
    assert resp.status_code == 302
