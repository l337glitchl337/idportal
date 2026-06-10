import secrets
import hmac
from flask import session, request, abort


def generate_csrf_token() -> str:
    if 'csrf_token' not in session:
        session['csrf_token'] = secrets.token_hex(32)
    return session['csrf_token']


def validate_csrf() -> None:
    if request.method != 'POST':
        return
    token = session.get('csrf_token')
    form_token = request.form.get('csrf_token') or request.headers.get('X-CSRF-Token')
    if not token or not form_token or not hmac.compare_digest(token, form_token):
        abort(400, description="Invalid or missing CSRF token.")
