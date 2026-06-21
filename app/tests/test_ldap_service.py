import pytest
from unittest.mock import MagicMock, patch
from flask import Flask
from services.ldap_service import LDAPService


@pytest.fixture
def app():
    a = Flask(__name__)
    a.config.update({
        'TESTING': True,
        'SECRET_KEY': 'ldap-test',
        'LDAP_URI': 'ldap://localhost',
        'LDAP_BIND_DN': 'cn=svc,dc=example,dc=com',
        'LDAP_BIND_PWD': 'svcpass',
        'LDAP_SEARCH_BASE': 'dc=example,dc=com',
        'LDAP_SEARCH_FILTER': '(mail={0})',
        'LDAP_ATTRIBUTES': '{"First Name": "givenName", "Last Name": "sn", "Email": "mail", "ID Number": "employeeNumber", "Location": "l", "cn": "cn"}',
        'LDAP_USE_TLS': False,
        'LDAP_TLS_CACERTFILE': None,
    })
    return a


@pytest.fixture
def auth_svc():
    return MagicMock()


@pytest.fixture
def db():
    return MagicMock()


@pytest.fixture
def svc(app, auth_svc, db):
    return LDAPService(auth_service=auth_svc, app=app, db=db)


# ── auth_user ────────────────────────────────────────────────────────────────

def test_auth_user_empty_password_rejected(app, svc, auth_svc, db):
    auth_svc.check_bfa.return_value = True
    db.execute_query.return_value = (0,)  # no pending submissions
    with patch.object(svc, 'search_user', return_value=('cn=user,dc=example,dc=com', {'Email': 'u@x.com'})), \
         patch.object(svc, 'check_user_submissions', return_value=True):
        with app.test_request_context('/'):
            msg, attrs, result = svc.auth_user('u@x.com', '')
    assert result is False
    assert attrs is None


def test_auth_user_none_password_rejected(app, svc, auth_svc):
    auth_svc.check_bfa.return_value = True
    with patch.object(svc, 'search_user', return_value=('cn=user,dc=example,dc=com', {'Email': 'u@x.com'})), \
         patch.object(svc, 'check_user_submissions', return_value=True):
        with app.test_request_context('/'):
            msg, attrs, result = svc.auth_user('u@x.com', None)
    assert result is False
    assert attrs is None


def test_auth_user_bfa_blocked_returns_false(app, svc, auth_svc):
    auth_svc.check_bfa.return_value = False
    with app.test_request_context('/'):
        msg, attrs, result = svc.auth_user('u@x.com', 'somepass')
    assert result is False


def test_auth_user_pending_submission_blocked(app, svc, auth_svc):
    auth_svc.check_bfa.return_value = True
    with patch.object(svc, 'check_user_submissions', return_value=False):
        with app.test_request_context('/'):
            msg, attrs, result = svc.auth_user('u@x.com', 'somepass')
    assert result is False
    assert 'pending' in msg.lower() or 'approved' in msg.lower()


def test_auth_user_user_not_found_returns_false(app, svc, auth_svc):
    auth_svc.check_bfa.return_value = True
    with patch.object(svc, 'check_user_submissions', return_value=True), \
         patch.object(svc, 'search_user', return_value=(None, {})):
        with app.test_request_context('/'):
            msg, attrs, result = svc.auth_user('u@x.com', 'somepass')
    assert result is False
