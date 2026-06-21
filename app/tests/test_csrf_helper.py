import pytest
from flask import Flask, session
from helpers.csrf_helper import generate_csrf_token, validate_csrf


@pytest.fixture
def app():
    a = Flask(__name__)
    a.config.update({'TESTING': True, 'SECRET_KEY': 'csrf-test-secret'})

    @a.route('/protected', methods=['GET', 'POST'])
    def protected():
        validate_csrf()
        return 'ok', 200

    return a


@pytest.fixture
def client(app):
    return app.test_client()


# ── generate_csrf_token ──────────────────────────────────────────────────────

def test_generate_csrf_token_creates_token(app):
    with app.test_request_context('/'):
        token = generate_csrf_token()
        assert token is not None
        assert len(token) == 64  # secrets.token_hex(32) = 64 hex chars


def test_generate_csrf_token_reuses_existing(app):
    with app.test_request_context('/'):
        session['csrf_token'] = 'existing-token'
        token = generate_csrf_token()
        assert token == 'existing-token'


def test_generate_csrf_token_unique_per_session(app):
    with app.test_request_context('/'):
        t1 = generate_csrf_token()
    with app.test_request_context('/'):
        t2 = generate_csrf_token()
    assert t1 != t2


# ── validate_csrf: GET passthrough ───────────────────────────────────────────

def test_get_request_passes_without_token(client):
    assert client.get('/protected').status_code == 200


# ── validate_csrf: POST with form token ─────────────────────────────────────

def test_post_matching_form_token_succeeds(client):
    with client.session_transaction() as sess:
        sess['csrf_token'] = 'good-token'
    resp = client.post('/protected', data={'csrf_token': 'good-token'})
    assert resp.status_code == 200


def test_post_wrong_form_token_fails(client):
    with client.session_transaction() as sess:
        sess['csrf_token'] = 'correct'
    resp = client.post('/protected', data={'csrf_token': 'wrong'})
    assert resp.status_code == 400


def test_post_missing_token_fails(client):
    with client.session_transaction() as sess:
        sess['csrf_token'] = 'expected'
    resp = client.post('/protected', data={})
    assert resp.status_code == 400


def test_post_no_session_token_fails(client):
    resp = client.post('/protected', data={'csrf_token': 'anything'})
    assert resp.status_code == 400


# ── validate_csrf: POST with header token ────────────────────────────────────

def test_post_matching_header_token_succeeds(client):
    with client.session_transaction() as sess:
        sess['csrf_token'] = 'hdr-tok'
    resp = client.post('/protected', headers={'X-CSRF-Token': 'hdr-tok'})
    assert resp.status_code == 200


def test_post_wrong_header_token_fails(client):
    with client.session_transaction() as sess:
        sess['csrf_token'] = 'correct'
    resp = client.post('/protected', headers={'X-CSRF-Token': 'wrong'})
    assert resp.status_code == 400
