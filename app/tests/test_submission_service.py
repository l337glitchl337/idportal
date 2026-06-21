import pytest
from unittest.mock import MagicMock
from flask import Flask, session
from services.submission_service import SubmissionService


@pytest.fixture
def app():
    a = Flask(__name__)
    a.config.update({'TESTING': True, 'SECRET_KEY': 'sub-svc-test'})
    return a


@pytest.fixture
def db():
    return MagicMock()


@pytest.fixture
def mail():
    return MagicMock()


@pytest.fixture
def svc(db, mail):
    return SubmissionService(db=db, mail=mail)


def _user_session(sess):
    sess['First Name'] = 'Alice'
    sess['Last Name'] = 'Smith'
    sess['ID Number'] = 'EMP001'
    sess['Location'] = 'HQ'
    sess['Email'] = 'alice@example.com'


# ── create_submission ─────────────────────────────────────────────────────────

def test_create_submission_success(app, svc, db):
    db.execute_query.return_value = (99,)
    with app.test_request_context('/'):
        _user_session(session)
        result = svc.create_submission("photo.jpg", "license.jpg")
    assert result is True


def test_create_submission_db_failure(app, svc, db):
    db.execute_query.return_value = None
    with app.test_request_context('/'):
        _user_session(session)
        result = svc.create_submission("photo.jpg", "license.jpg")
    assert result is False


def test_create_submission_stores_request_id_in_session(app, svc, db):
    db.execute_query.return_value = (42,)
    with app.test_request_context('/'):
        _user_session(session)
        svc.create_submission("p.jpg", "l.jpg")
        assert session.get('request_id') == 42


# ── approve_request ────────────────────────────────────────────────────────────

def test_approve_request_success(svc, db, mail):
    db.execute_query.return_value = True
    result = svc.approve_request("123", actor="admin1")
    assert result is True
    mail.send_approved_email.assert_called_once_with("123")


def test_approve_request_db_failure(svc, db, mail):
    db.execute_query.return_value = False
    result = svc.approve_request("123", actor="admin1")
    assert result is False
    mail.send_approved_email.assert_not_called()


# ── reject_request ─────────────────────────────────────────────────────────────

def test_reject_request_success(svc, db, mail):
    db.execute_query.return_value = True
    result = svc.reject_request("456", "Missing docs", actor="admin1")
    assert result is True
    mail.send_rejection_email.assert_called_once_with("456", "Missing docs")


def test_reject_request_db_failure(svc, db, mail):
    db.execute_query.return_value = False
    result = svc.reject_request("456", "Missing docs", actor="admin1")
    assert result is False
    mail.send_rejection_email.assert_not_called()


# ── search ─────────────────────────────────────────────────────────────────────

def test_search_returns_results(svc, db):
    db.execute_query.side_effect = [
        (3,),                    # count
        [{'request_id': 1}, {'request_id': 2}, {'request_id': 3}],
    ]
    result = svc.search("alice", page=1)
    assert result is not None
    assert len(result['search_results']) == 3


def test_search_no_results_returns_none(svc, db):
    db.execute_query.return_value = (0,)
    result = svc.search("nobody")
    assert result is None


def test_search_pagination_next_page(svc, db):
    db.execute_query.side_effect = [
        (30,),  # 2 pages at 15 per page
        [],
    ]
    result = svc.search("term", page=1)
    assert result['search_pagination']['next_page'] == 2
    assert result['search_pagination']['prev_page'] is None


def test_search_pagination_last_page(svc, db):
    db.execute_query.side_effect = [
        (30,),
        [],
    ]
    result = svc.search("term", page=2)
    assert result['search_pagination']['next_page'] is None
    assert result['search_pagination']['prev_page'] == 1


# ── delete ─────────────────────────────────────────────────────────────────────

def test_delete_success(svc, db):
    db.execute_query.return_value = True
    result = svc.delete("789", actor="admin1")
    assert result is True
    db.execute_query.assert_called_once_with(
        "delete from submissions where request_id=%s", ("789",)
    )


def test_delete_db_failure(svc, db):
    db.execute_query.return_value = False
    result = svc.delete("789", actor="admin1")
    assert result is False
