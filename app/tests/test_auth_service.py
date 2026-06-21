import bcrypt
import pytest
from unittest.mock import MagicMock
from flask import Flask, session
from services.auth_service import AuthService


@pytest.fixture
def app():
    a = Flask(__name__)
    a.config.update({
        'TESTING': True,
        'SECRET_KEY': 'auth-test-secret',
        'FORGOT_PASSWORD_URL': 'https://example.com/forgot_password',
    })
    return a


@pytest.fixture
def db():
    return MagicMock()


@pytest.fixture
def svc(db):
    return AuthService(db=db)


def _hash(pw: str) -> str:
    return bcrypt.hashpw(pw.encode(), bcrypt.gensalt()).decode()


def _req_ctx(app, ip='127.0.0.1'):
    return app.test_request_context('/', environ_base={'REMOTE_ADDR': ip})


# ── admin_login ──────────────────────────────────────────────────────────────
# check_bfa is called first: execute_query("select * from bfa") → None means no record
# then the admins SELECT uses the next side_effect entry.

def test_admin_login_success(app, svc, db):
    hashed = _hash("Password1!")
    db.execute_query.side_effect = [
        None,  # check_bfa: no bfa record → returns True
        ("First", "Last", "user", "u@e.com", hashed, 1, "super", 0, 42),
    ]
    with _req_ctx(app):
        result = svc.admin_login("user", "Password1!")
        assert session.get('admin_username') == 'user'
        assert session.get('role') == 'super'
    assert result is True


def test_admin_login_user_not_found(app, svc, db):
    db.execute_query.side_effect = [None, None]
    with _req_ctx(app):
        result = svc.admin_login("nobody", "pass")
    assert result is False


def test_admin_login_account_disabled(app, svc, db):
    hashed = _hash("Password1!")
    db.execute_query.side_effect = [
        None,
        ("First", "Last", "user", "u@e.com", hashed, 0, "super", 0, 1),
    ]
    with _req_ctx(app):
        result = svc.admin_login("user", "Password1!")
    assert result is False


def test_admin_login_wrong_password(app, svc, db):
    hashed = _hash("CorrectPass1!")
    db.execute_query.side_effect = [
        None,   # first check_bfa: no record → allowed
        ("First", "Last", "user", "u@e.com", hashed, 1, "super", 0, 1),
        None,   # second check_bfa (failed=True): no record → select
        None,   # insert new bfa record
    ]
    with _req_ctx(app):
        result = svc.admin_login("user", "WrongPass1!")
    assert result is False


def test_admin_login_bfa_locked(app, svc, db):
    # BFA row exists with 3 failures → check_bfa returns False → login blocked
    db.execute_query.side_effect = [
        (None, None, None, 3, None),  # bfa row: row[3]=3
        (False,),                     # is_older = False (still within 30 min)
        ("2026-01-01 00:30:00",),     # unlock time
    ]
    with _req_ctx(app):
        result = svc.admin_login("user", "Password1!")
    assert result is False


# ── update_admin_password ────────────────────────────────────────────────────

def test_update_admin_password_success(app, svc, db):
    old_hashed = _hash("OldPass1!")
    db.execute_query.side_effect = [(old_hashed,), True]
    with app.test_request_context('/'):
        result = svc.update_admin_password("user", "NewPass1!")
    assert result is True


def test_update_admin_password_same_as_old(app, svc, db):
    same = "SamePass1!"
    db.execute_query.return_value = (_hash(same),)
    with app.test_request_context('/'):
        result = svc.update_admin_password("user", same)
    assert result is False


def test_update_admin_password_fails_complexity(app, svc, db):
    with app.test_request_context('/'):
        result = svc.update_admin_password("user", "weak")
    assert result is False
    db.execute_query.assert_not_called()


def test_update_admin_password_user_not_found(app, svc, db):
    db.execute_query.return_value = None
    with app.test_request_context('/'):
        result = svc.update_admin_password("ghost", "NewPass1!")
    assert result is False


# ── compare_password ─────────────────────────────────────────────────────────

def test_compare_password_match(svc, db):
    hashed = _hash("MyPass1!")
    db.execute_query.return_value = (hashed,)
    assert svc.compare_password("user", "MyPass1!") is True


def test_compare_password_no_match(svc, db):
    hashed = _hash("MyPass1!")
    db.execute_query.return_value = (hashed,)
    assert svc.compare_password("user", "WrongPass1!") is False


def test_compare_password_user_not_found(svc, db):
    db.execute_query.return_value = None
    assert svc.compare_password("ghost", "MyPass1!") is False


# ── token helpers ────────────────────────────────────────────────────────────

def test_gen_random_forgot_password_link_format(app, svc):
    with app.test_request_context('/'):
        url, token = svc.gen_random_forgot_password_link()
    assert token in url
    assert 'forgot_password' in url
    assert len(token) == 32


def test_validate_forgot_password_token_valid(svc, db):
    db.execute_query.return_value = ("someuser",)
    result = svc.validate_forgot_password_token("abc123")
    assert result == "someuser"


def test_validate_forgot_password_token_invalid(svc, db):
    db.execute_query.return_value = None
    assert svc.validate_forgot_password_token("badtoken") is False


def test_del_forgot_password_token(svc, db):
    result = svc.del_forgot_password_token("sometoken")
    assert result is True
    db.execute_query.assert_called_once()


# ── set_session_attrs ────────────────────────────────────────────────────────

def test_set_session_attrs_sets_keys(app, svc):
    attrs = {'First Name': 'Alice', 'Email': 'alice@example.com'}
    with app.test_request_context('/'):
        result = svc.set_session_attrs(attrs)
        assert session.get('First Name') == 'Alice'
    assert result is True


def test_set_session_attrs_marks_user_logged_in(app, svc):
    with app.test_request_context('/'):
        svc.set_session_attrs({'Email': 'x@x.com'})
        assert session.get('user_logged_in') is True


# ── entra_admin_login ─────────────────────────────────────────────────────────

def test_entra_admin_login_success(app, svc, db):
    db.execute_query.side_effect = [
        ("First", "Last", "admin", "a@b.com", 1, "super", 0, 7),
        None,  # UPDATE name
    ]
    userinfo = {'email': 'a@b.com', 'given_name': 'First', 'family_name': 'Last'}
    with app.test_request_context('/'):
        result = svc.entra_admin_login(userinfo)
        assert session.get('admin_username') == 'admin'
        assert session.get('role') == 'super'
    assert result is True


def test_entra_admin_login_not_provisioned(app, svc, db):
    db.execute_query.return_value = None
    with app.test_request_context('/'):
        result = svc.entra_admin_login({'email': 'unknown@b.com'})
    assert result is False


def test_entra_admin_login_account_disabled(app, svc, db):
    db.execute_query.return_value = ("F", "L", "admin", "a@b.com", 0, "super", 0, 7)
    with app.test_request_context('/'):
        result = svc.entra_admin_login({'email': 'a@b.com'})
    assert result is False


def test_entra_admin_login_uses_preferred_username_fallback(app, svc, db):
    db.execute_query.side_effect = [
        ("F", "L", "admin", "a@b.com", 1, "manager", 0, 3),
        None,
    ]
    userinfo = {'preferred_username': 'a@b.com', 'given_name': 'F', 'family_name': 'L'}
    with app.test_request_context('/'):
        result = svc.entra_admin_login(userinfo)
    assert result is True


# ── entra_user_login ──────────────────────────────────────────────────────────

def test_entra_user_login_sets_session(app, svc):
    userinfo = {
        'email': 'u@example.com',
        'given_name': 'Jane',
        'family_name': 'Doe',
        'preferred_username': 'u@example.com',
    }
    with app.test_request_context('/'):
        result = svc.entra_user_login(userinfo)
        assert session.get('user_logged_in') is True
    assert result is True


# ── check_bfa ────────────────────────────────────────────────────────────────

def test_check_bfa_no_record_success_allowed(svc, db):
    db.execute_query.return_value = None
    assert svc.check_bfa("user@x.com", "1.2.3.4", False) is True


def test_check_bfa_no_record_failed_inserts_row(svc, db):
    db.execute_query.return_value = None
    svc.check_bfa("user@x.com", "1.2.3.4", True)
    assert db.execute_query.call_count == 2  # select + insert


def test_check_bfa_under_limit_failed_increments(svc, db):
    db.execute_query.side_effect = [
        (None, None, None, 2),  # existing row with 2 failures
        None,                   # update
    ]
    result = svc.check_bfa("user@x.com", "1.2.3.4", True)
    assert result is True


def test_check_bfa_at_limit_within_30min_blocked(svc, db):
    db.execute_query.side_effect = [
        (None, None, None, 3),  # 3 failures
        (False,),               # not older than 30 min → still locked
        ("2026-01-01 00:30:00",),
    ]
    result = svc.check_bfa("user@x.com", "1.2.3.4", False)
    assert result is False


def test_check_bfa_at_limit_after_30min_resets(svc, db):
    db.execute_query.side_effect = [
        (None, None, None, 3),  # 3 failures
        (True,),                # older than 30 min → unlocked
        None,                   # delete from bfa
    ]
    result = svc.check_bfa("user@x.com", "1.2.3.4", False)
    assert result is True
