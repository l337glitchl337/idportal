from functools import wraps
from flask import session, redirect, url_for, flash, request

class DecoratorHelper:
    @staticmethod
    def check_login(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            if 'user_logged_in' in session and session['user_logged_in']:
                return f(*args, **kwargs)
            flash("Please login first", "danger")
            return redirect(url_for("user.home"))
        return decorated
    
    @staticmethod
    def check_admin_login(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            # Allow access to change_admin_password if forgot_password_token is set
            if 'forgot_password_token' in session:
                if request.endpoint == "admin.change_admin_password":
                    return f(*args, **kwargs)
                else:
                    return redirect(url_for("admin.admin"))
            if 'admin_username' not in session:
                flash("Please login first", "danger")
                return redirect(url_for("admin.admin"))
            return f(*args, **kwargs)
        return decorated

    @staticmethod
    def check_first_login(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            if session["on_login"] == 1:
                flash("Please change your password first!", "danger")
                return redirect(url_for("admin.admin"))
            return f(*args, **kwargs)
        return decorated
