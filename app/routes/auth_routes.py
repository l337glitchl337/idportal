from flask import Blueprint, redirect, url_for, session, flash, current_app, request
from authlib.integrations.flask_client import OAuth

auth_blueprint = Blueprint('auth', __name__)
oauth = OAuth()


def init_oauth(app):
    oauth.init_app(app)
    tenant_id = app.config.get('ENTRA_TENANT_ID', '')
    oauth.register(
        name='entra',
        client_id=app.config.get('ENTRA_CLIENT_ID'),
        client_secret=app.config.get('ENTRA_CLIENT_SECRET'),
        server_metadata_url=(
            f'https://login.microsoftonline.com/{tenant_id}/v2.0'
            '/.well-known/openid-configuration'
        ),
        client_kwargs={'scope': 'openid email profile'},
    )


@auth_blueprint.route('/oauth/login')
def oauth_login():
    if not current_app.config.get('ENTRA_CLIENT_ID'):
        flash('Microsoft sign-in is not configured.', 'danger')
        flow = request.args.get('flow', 'user')
        return redirect(url_for('admin.admin') if flow == 'admin' else url_for('user.home'))

    flow = request.args.get('flow', 'user')

    if flow == 'admin' and current_app.config["ADMIN_AUTH_MODE"] == "local":
        flash("Microsoft sign-in is not enabled for admins.", "danger")
        return redirect(url_for('admin.admin'))
    if flow == 'user' and current_app.config["USER_AUTH_MODE"] == "ldap":
        flash("Microsoft sign-in is not enabled.", "danger")
        return redirect(url_for('user.home'))

    session['oauth_flow'] = flow
    redirect_uri = url_for('auth.oauth_callback', _external=True)
    return oauth.entra.authorize_redirect(redirect_uri)


@auth_blueprint.route('/oauth/callback')
def oauth_callback():
    try:
        token = oauth.entra.authorize_access_token()
    except Exception:
        current_app.logger.exception('OAuth callback error')
        flash('Sign-in failed. Please try again.', 'danger')
        return redirect(url_for('user.home'))

    userinfo = token.get('userinfo') or {}
    flow = session.pop('oauth_flow', 'user')
    auth_service = current_app.auth_service

    if flow == 'admin':
        if auth_service.entra_admin_login(userinfo):
            return redirect(url_for('admin.admin_panel'))
        return redirect(url_for('admin.admin'))

    if auth_service.entra_user_login(userinfo):
        return redirect(url_for('user.landing'))
    return redirect(url_for('user.home'))
