import pytest
from unittest.mock import patch, MagicMock
from tests.conftest import make_app


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
        sess['email'] = 'admin@example.com'
        sess['role'] = 'super'
        sess['on_login'] = 0
        sess['user_id'] = 1
    return c


@pytest.fixture
def manager_client(app):
    c = app.test_client()
    with c.session_transaction() as sess:
        sess['admin_username'] = 'mgr'
        sess['role'] = 'manager'
        sess['on_login'] = 0
        sess['user_id'] = 2
        sess['first_name'] = 'M'
        sess['last_name'] = 'G'
        sess['email'] = 'mgr@example.com'
    return c


# ── GET /admin ────────────────────────────────────────────────────────────────

def test_get_admin_renders_login(client):
    with patch('routes.admin_routes.render_template', return_value='') as mock_rt:
        resp = client.get('/admin')
    assert resp.status_code == 200
    mock_rt.assert_called_once_with('admin.html')


# ── POST /admin (local auth) ──────────────────────────────────────────────────

def test_post_admin_login_success(app, client):
    app.auth_service.admin_login.return_value = True
    with app.test_client() as c:
        with c.session_transaction() as sess:
            sess['on_login'] = 0
        with patch('routes.admin_routes.session', dict(on_login=0)):
            resp = client.post('/admin', data={'username': 'admin', 'password': 'pass'})
    assert resp.status_code == 302
    assert '/admin_panel' in resp.headers['Location']


def test_post_admin_login_failure(app, client):
    app.auth_service.admin_login.return_value = False
    resp = client.post('/admin', data={'username': 'admin', 'password': 'wrong'})
    assert resp.status_code == 302
    assert '/admin' in resp.headers['Location']


def test_post_admin_login_blocked_in_entra_mode(app, client):
    app.config['ADMIN_AUTH_MODE'] = 'entra'
    resp = client.post('/admin', data={'username': 'admin', 'password': 'pass'})
    assert resp.status_code == 302
    assert '/admin' in resp.headers['Location']
    app.config['ADMIN_AUTH_MODE'] = 'local'


def test_post_admin_login_first_login_redirect(app, client):
    app.auth_service.admin_login.return_value = True
    with patch('routes.admin_routes.session', {'on_login': 1}):
        resp = client.post('/admin', data={'username': 'admin', 'password': 'pass'})
    assert resp.status_code == 302


# ── GET /admin_panel ──────────────────────────────────────────────────────────

def test_get_admin_panel_unauthenticated(client):
    resp = client.get('/admin_panel')
    assert resp.status_code == 302
    assert '/admin' in resp.headers['Location']


def test_get_admin_panel_authenticated(app, admin_client):
    app.admin_service.populate_admin_panel.return_value = {
        'pending_requests': [],
        'pending_pagination': {'total_pages': 1, 'next_page': None, 'prev_page': None},
    }
    with patch('routes.admin_routes.render_template', return_value=''):
        resp = admin_client.get('/admin_panel?active_tab=pending')
    assert resp.status_code == 200


def test_get_admin_panel_search(app, admin_client):
    app.submission_service.search.return_value = {
        'search_results': [{'request_id': 1}],
        'search_pagination': {'total_pages': 1, 'next_page': None, 'prev_page': None},
    }
    with patch('routes.admin_routes.render_template', return_value=''):
        resp = admin_client.get('/admin_panel?search_term=alice')
    assert resp.status_code == 200


def test_get_admin_panel_search_no_results(app, admin_client):
    app.submission_service.search.return_value = None
    resp = admin_client.get('/admin_panel?search_term=nobody')
    assert resp.status_code == 302


# ── POST /logout ──────────────────────────────────────────────────────────────

def test_logout_admin_clears_session(admin_client):
    resp = admin_client.post('/logout')
    assert resp.status_code == 302
    assert '/admin' in resp.headers['Location']


def test_logout_get_not_allowed(client):
    resp = client.get('/logout')
    assert resp.status_code == 405


def test_logout_user_redirects_home(client):
    with client.session_transaction() as sess:
        sess['user_logged_in'] = True
    resp = client.post('/logout')
    assert resp.status_code == 302


# ── POST /reject_submission ────────────────────────────────────────────────────

def test_reject_submission_success(app, admin_client):
    app.submission_service.reject_request.return_value = True
    resp = admin_client.post('/reject_submission',
                             data={'request_id': '1', 'comments': 'Bad photo'})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data['success'] is True


def test_reject_submission_failure(app, admin_client):
    app.submission_service.reject_request.return_value = False
    resp = admin_client.post('/reject_submission',
                             data={'request_id': '1', 'comments': ''})
    assert resp.get_json()['success'] is False


def test_reject_submission_comment_too_long(admin_client):
    resp = admin_client.post('/reject_submission',
                             data={'request_id': '1', 'comments': 'x' * 251})
    assert resp.get_json()['success'] is False
    assert '250' in resp.get_json()['message']


def test_reject_submission_unauthenticated(client):
    resp = client.post('/reject_submission',
                       data={'request_id': '1', 'comments': ''})
    assert resp.status_code == 302


# ── POST /approve_submission ───────────────────────────────────────────────────

def test_approve_submission_success(app, admin_client):
    app.submission_service.approve_request.return_value = True
    resp = admin_client.post('/approve_submission', data={'request_id': '1'})
    assert resp.get_json()['success'] is True


def test_approve_submission_failure(app, admin_client):
    app.submission_service.approve_request.return_value = False
    resp = admin_client.post('/approve_submission', data={'request_id': '1'})
    assert resp.get_json()['success'] is False


# ── POST /create_admin_account ────────────────────────────────────────────────

def test_create_admin_local_mode_success(app, admin_client):
    app.admin_service.create_admin.return_value = True
    resp = admin_client.post('/create_admin_account', data={
        'first_name': 'Bob',
        'last_name': 'Jones',
        'username': 'bjones',
        'email': 'b@example.com',
        'role': 'manager',
    })
    assert resp.status_code == 302
    app.admin_service.create_admin.assert_called_once()


def test_create_admin_local_invalid_first_name(admin_client):
    resp = admin_client.post('/create_admin_account', data={
        'first_name': 'B0b!',
        'last_name': 'Jones',
        'username': 'bjones',
        'email': 'b@example.com',
        'role': 'manager',
    })
    assert resp.status_code == 302


def test_create_admin_invalid_email(admin_client):
    resp = admin_client.post('/create_admin_account', data={
        'first_name': 'Bob',
        'last_name': 'Jones',
        'username': 'bjones',
        'email': 'not-an-email',
        'role': 'manager',
    })
    assert resp.status_code == 302


def test_create_admin_invalid_role(admin_client):
    resp = admin_client.post('/create_admin_account', data={
        'first_name': 'Bob',
        'last_name': 'Jones',
        'username': 'bjones',
        'email': 'b@example.com',
        'role': 'superadmin',
    })
    assert resp.status_code == 302


def test_create_admin_entra_mode_only_needs_email_role(app, admin_client):
    app.config['ADMIN_AUTH_MODE'] = 'entra'
    app.admin_service.create_admin.return_value = True
    resp = admin_client.post('/create_admin_account', data={
        'email': 'newadmin@example.com',
        'role': 'manager',
    })
    assert resp.status_code == 302
    app.admin_service.create_admin.assert_called_once()
    app.config['ADMIN_AUTH_MODE'] = 'local'


def test_create_admin_blocked_for_non_super(app, manager_client):
    resp = manager_client.post('/create_admin_account', data={
        'first_name': 'Bob', 'last_name': 'Jones',
        'username': 'bjones', 'email': 'b@example.com', 'role': 'manager',
    })
    assert resp.status_code == 302
    app.admin_service.create_admin.assert_not_called()


# ── POST /edit_admin_account ───────────────────────────────────────────────────

def test_edit_admin_success(app, admin_client):
    app.admin_service.edit_admin.return_value = True
    resp = admin_client.post('/edit_admin_account', data={
        'user_id': '5',
        'first_name': 'Alice',
        'last_name': 'Smith',
        'username': 'asmith',
        'email': 'a@example.com',
        'role': 'manager',
    })
    assert resp.status_code == 302


def test_edit_admin_self_edit_blocked(app, admin_client):
    # admin_client has user_id=1; trying to edit user_id=1 is blocked
    resp = admin_client.post('/edit_admin_account', data={
        'user_id': '1',
        'first_name': 'Test',
        'last_name': 'Admin',
        'username': 'testadmin',
        'email': 'admin@example.com',
        'role': 'super',
    })
    assert resp.status_code == 302


def test_edit_admin_blocked_for_non_super(app, manager_client):
    resp = manager_client.post('/edit_admin_account', data={
        'user_id': '5',
        'first_name': 'A', 'last_name': 'B',
        'username': 'ab', 'email': 'a@b.com', 'role': 'manager',
    })
    assert resp.status_code == 302
    app.admin_service.edit_admin.assert_not_called()


# ── POST /delete_admin_account ────────────────────────────────────────────────

def test_delete_admin_success(app, admin_client):
    app.admin_service.delete_admin.return_value = True
    resp = admin_client.post('/delete_admin_account', data={'user_id': '5'})
    assert resp.get_json()['success'] is True


def test_delete_admin_self_delete_blocked(admin_client):
    resp = admin_client.post('/delete_admin_account', data={'user_id': '1'})
    assert resp.get_json()['success'] is False


def test_delete_admin_blocked_for_non_super(app, manager_client):
    resp = manager_client.post('/delete_admin_account', data={'user_id': '5'})
    assert resp.get_json()['success'] is False
    app.admin_service.delete_admin.assert_not_called()


def test_delete_admin_invalid_id(admin_client):
    resp = admin_client.post('/delete_admin_account', data={'user_id': 'abc'})
    assert resp.get_json()['success'] is False


# ── POST /batch_edit ──────────────────────────────────────────────────────────

def test_batch_approve_success(app, admin_client):
    app.submission_service.approve_request.return_value = True
    resp = admin_client.post('/batch_edit',
                             data={'action': 'approve', 'request_ids': ['1', '2', '3']})
    assert resp.get_json()['success'] is True
    assert app.submission_service.approve_request.call_count == 3


def test_batch_reject_success(app, admin_client):
    app.submission_service.reject_request.return_value = True
    resp = admin_client.post('/batch_edit', data={
        'action': 'reject',
        'request_ids': ['1', '2'],
        'comments': 'Batch reject',
    })
    assert resp.get_json()['success'] is True


def test_batch_reject_comment_too_long(admin_client):
    resp = admin_client.post('/batch_edit', data={
        'action': 'reject',
        'request_ids': ['1'],
        'comments': 'x' * 251,
    })
    assert resp.get_json()['success'] is False


def test_batch_approve_partial_failure(app, admin_client):
    app.submission_service.approve_request.side_effect = [True, False, True]
    resp = admin_client.post('/batch_edit',
                             data={'action': 'approve', 'request_ids': ['1', '2', '3']})
    assert resp.get_json()['success'] is False


# ── POST /delete_submission ───────────────────────────────────────────────────

def test_delete_submission_success(app, admin_client):
    app.submission_service.delete.return_value = True
    resp = admin_client.post('/delete_submission', data={'request_id': '10'})
    assert resp.get_json()['success'] is True


def test_delete_submission_failure(app, admin_client):
    app.submission_service.delete.return_value = False
    resp = admin_client.post('/delete_submission', data={'request_id': '10'})
    assert resp.get_json()['success'] is False


# ── GET /forgot_password ───────────────────────────────────────────────────────

def test_get_forgot_password_renders_form(client):
    with patch('routes.admin_routes.render_template', return_value=''):
        resp = client.get('/forgot_password')
    assert resp.status_code == 200


def test_get_forgot_password_blocked_in_entra_mode(app, client):
    app.config['ADMIN_AUTH_MODE'] = 'entra'
    resp = client.get('/forgot_password')
    assert resp.status_code == 302
    app.config['ADMIN_AUTH_MODE'] = 'local'


def test_post_forgot_password_with_email(app, client):
    app.email_service.send_forgot_password_email.return_value = True
    with patch('routes.admin_routes.forgot_password_limiter') as mock_lim:
        mock_lim.is_allowed.return_value = True
        resp = client.post('/forgot_password', data={'identifier': 'admin@example.com'})
    assert resp.status_code == 302
    assert '/admin' in resp.headers['Location']


def test_post_forgot_password_rate_limited(app, client):
    with patch('routes.admin_routes.forgot_password_limiter') as mock_lim:
        mock_lim.is_allowed.return_value = False
        resp = client.post('/forgot_password', data={'identifier': 'admin@example.com'})
    assert resp.status_code == 302


def test_get_forgot_password_valid_token(app, client):
    app.auth_service.validate_forgot_password_token.return_value = 'admin'
    resp = client.get('/forgot_password?token=validtoken')
    assert resp.status_code == 302
    assert '/change_admin_password' in resp.headers['Location']


def test_get_forgot_password_invalid_token(app, client):
    app.auth_service.validate_forgot_password_token.return_value = False
    resp = client.get('/forgot_password?token=badtoken')
    assert resp.status_code == 302
    assert '/admin' in resp.headers['Location']


# ── GET /change_admin_password ────────────────────────────────────────────────

def test_change_password_get_renders(admin_client):
    with patch('routes.admin_routes.render_template', return_value=''):
        resp = admin_client.get('/change_admin_password')
    assert resp.status_code == 200


def test_change_password_blocked_in_entra_mode(app, admin_client):
    app.config['ADMIN_AUTH_MODE'] = 'entra'
    resp = admin_client.get('/change_admin_password')
    assert resp.status_code == 302
    app.config['ADMIN_AUTH_MODE'] = 'local'


def test_change_password_post_success(app, admin_client):
    app.auth_service.compare_password.return_value = True
    app.auth_service.update_admin_password.return_value = True
    resp = admin_client.post('/change_admin_password', data={
        'current_password': 'OldPass1!',
        'new_password': 'NewPass1!',
        'confirm_password': 'NewPass1!',
    })
    assert resp.status_code == 302
    assert '/admin' in resp.headers['Location']


def test_change_password_post_passwords_mismatch(app, admin_client):
    app.auth_service.compare_password.return_value = True
    resp = admin_client.post('/change_admin_password', data={
        'current_password': 'OldPass1!',
        'new_password': 'NewPass1!',
        'confirm_password': 'DifferentPass1!',
    })
    assert resp.status_code == 302
    assert '/change_admin_password' in resp.headers['Location']


def test_change_password_post_wrong_current(app, admin_client):
    app.auth_service.compare_password.return_value = False
    resp = admin_client.post('/change_admin_password', data={
        'current_password': 'wrong',
        'new_password': 'NewPass1!',
        'confirm_password': 'NewPass1!',
    })
    assert resp.status_code == 302
