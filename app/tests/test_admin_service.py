import pytest
from unittest.mock import MagicMock, call
from flask import Flask, session
from services.admin_service import AdminService


@pytest.fixture
def app():
    a = Flask(__name__)
    a.config.update({'TESTING': True, 'SECRET_KEY': 'admin-svc-test'})
    return a


@pytest.fixture
def db():
    return MagicMock()


@pytest.fixture
def svc(db):
    return AdminService(db=db)


# ── create_admin ─────────────────────────────────────────────────────────────

def test_create_admin_success(svc, db):
    db.execute_query.return_value = True
    result = svc.create_admin("Alice", "Smith", "asmith", "a@b.com", "manager")
    assert result is True
    db.execute_query.assert_called_once()


def test_create_admin_db_failure_returns_none(svc, db):
    db.execute_query.return_value = False
    result = svc.create_admin("Alice", "Smith", "asmith", "a@b.com", "manager")
    # create_admin returns True on success but falls through (returns None) on failure
    assert not result


def test_create_admin_hashes_password(svc, db):
    db.execute_query.return_value = True
    svc.create_admin("A", "B", "ab", "a@b.com", "super")
    _, kwargs = db.execute_query.call_args
    # Not testing this via kwargs — just verify the call happened with a hashed pw
    args = db.execute_query.call_args[0]
    assert len(args) == 2  # SQL + params tuple
    params = args[1]
    assert params[0] == "A"  # first_name
    assert params[4] == "a@b.com"  # email
    # The hashed password should not equal the random token in plaintext
    assert len(params[3]) > 20  # bcrypt hash is 60 chars


# ── edit_admin ────────────────────────────────────────────────────────────────

def test_edit_admin_success(svc, db):
    db.execute_query.return_value = True
    result = svc.edit_admin(1, "Bob", "Jones", "bjones", "b@b.com", "manager")
    assert result is True


def test_edit_admin_db_failure(svc, db):
    db.execute_query.return_value = False
    result = svc.edit_admin(1, "Bob", "Jones", "bjones", "b@b.com", "manager")
    assert result is False


# ── delete_admin ──────────────────────────────────────────────────────────────

def test_delete_admin_success(svc, db):
    db.execute_query.return_value = True
    result = svc.delete_admin(5)
    assert result is True
    db.execute_query.assert_called_once_with("delete from admins where id=%s", (5,))


def test_delete_admin_db_failure(svc, db):
    db.execute_query.return_value = False
    result = svc.delete_admin(5)
    assert result is False


# ── populate_admin_panel ──────────────────────────────────────────────────────

def test_populate_admin_panel_pending_tab(app, svc, db):
    db.execute_query.side_effect = [
        (5,),    # count(*)
        [{'full_name': 'Alice Smith', 'request_id': 1}],
    ]
    with app.test_request_context('/'):
        session['role'] = 'super'
        result = svc.populate_admin_panel(page=1, active_tab='pending')
    assert 'pending_requests' in result
    assert 'pending_pagination' in result


def test_populate_admin_panel_pending_pagination(app, svc, db):
    db.execute_query.side_effect = [
        (45,),  # 45 total → 3 pages at 15 per page
        [],
    ]
    with app.test_request_context('/'):
        session['role'] = 'super'
        result = svc.populate_admin_panel(page=2, active_tab='pending')
    pag = result['pending_pagination']
    assert pag['total_pages'] == 3
    assert pag['prev_page'] == 1
    assert pag['next_page'] == 3


def test_populate_admin_panel_approved_tab(app, svc, db):
    db.execute_query.side_effect = [(0,), []]
    with app.test_request_context('/'):
        session['role'] = 'manager'
        result = svc.populate_admin_panel(page=1, active_tab='approved')
    assert 'approved_requests' in result


def test_populate_admin_panel_rejected_tab(app, svc, db):
    db.execute_query.side_effect = [(0,), []]
    with app.test_request_context('/'):
        session['role'] = 'manager'
        result = svc.populate_admin_panel(page=1, active_tab='rejected')
    assert 'rejected_requests' in result


def test_populate_admin_panel_admins_tab_super(app, svc, db):
    db.execute_query.side_effect = [
        (2,),  # count
        [{'full_name': 'Admin One', 'id': 1}, {'full_name': 'Admin Two', 'id': 2}],
    ]
    with app.test_request_context('/'):
        session['role'] = 'super'
        result = svc.populate_admin_panel(page=1, active_tab='admins')
    assert 'admins' in result
    assert len(result['admins']) == 2


def test_populate_admin_panel_admins_tab_non_super(app, svc, db):
    db.execute_query.return_value = (1,)
    with app.test_request_context('/'):
        session['role'] = 'manager'
        result = svc.populate_admin_panel(page=1, active_tab='admins')
    # Managers get an empty dict for the admins tab
    assert result == {}


def test_populate_admin_panel_unknown_tab(app, svc, db):
    with app.test_request_context('/'):
        session['role'] = 'super'
        result = svc.populate_admin_panel(page=1, active_tab='nonexistent')
    assert result == {'none': None}
