from flask import render_template, request, redirect, url_for, flash, Blueprint, current_app, session, send_from_directory
from helpers import DecoratorHelper, forgot_password_limiter
import traceback
import re
import os

_VALID_ROLES = {'manager', 'super'}
_MAX_COMMENT_LEN = 250
_NAME_RE = re.compile(r"^[A-Za-z\s'\-]{1,50}$")
_USERNAME_RE = re.compile(r"^[A-Za-z0-9_]{3,20}$")
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

admin_blueprint = Blueprint("admin", __name__)

@admin_blueprint.route("/admin", methods = ["POST", "GET"])
def admin():
    if request.method == "POST":
        if current_app.config["ADMIN_AUTH_MODE"] == "entra":
            flash("Password login is disabled. Use Microsoft sign-in.", "danger")
            return redirect(url_for("admin.admin"))
        username = request.form.get("username")
        password = request.form.get("password")
        auth_service = current_app.auth_service

        if auth_service.admin_login(username, password):
            if session["on_login"]:
                flash("Please change your password before proceeding", "danger")
                return redirect(url_for("admin.change_admin_password"))
            return redirect(url_for("admin.admin_panel", active_tab="pending"))
        else:
            flash("Invalid username/password combination", "danger")
            return redirect(url_for("admin.admin"))
    return render_template("admin.html")

@admin_blueprint.route("/admin_panel")
@DecoratorHelper.check_admin_login
@DecoratorHelper.check_first_login
def admin_panel():
    admin_service = current_app.admin_service
    submission_service = current_app.submission_service
    page = request.args.get("page", 1, type=int)
    active_tab = request.args.get("active_tab", "pending") 
    current_user = {"username": session["admin_username"], "role": session["role"], "email": session["email"], "user_id": session["user_id"]}

    if request.args.get("search_term"):
        results = submission_service.search(request.args.get("search_term"), page=page)
        if results:
            return render_template("admin_panel.html", active_tab=active_tab, **results, current_user=current_user, current_page=page)
        else:
            flash("No submissions found for that search term!", "info")
            return redirect(url_for("admin.admin_panel", active_tab="search"))
    data = admin_service.populate_admin_panel(page, active_tab=active_tab)
    return render_template("admin_panel.html", **data, active_tab=active_tab, current_user=current_user, current_page=page)

@admin_blueprint.route("/create_admin_account", methods = ["POST"])
@DecoratorHelper.check_admin_login
@DecoratorHelper.check_first_login
def create_admin_account():
    if session["role"] != "super":
        flash("You do not have permission to create admin accounts.", "danger")
        return redirect(url_for("admin.admin_panel", active_tab="admins"))
    admin_service = current_app.admin_service
    email_service = current_app.email_service
    email = request.form.get("email", "").strip()
    role = request.form.get("role", "").strip()

    entra_only = current_app.config["ADMIN_AUTH_MODE"] == "entra"
    if entra_only:
        first_name = "Pending"
        last_name = ""
        username = re.sub(r'[^A-Za-z0-9_]', '', email.split('@')[0])[:20] or "admin"
    else:
        first_name = request.form.get("first_name", "").strip()
        last_name = request.form.get("last_name", "").strip()
        username = request.form.get("username", "").strip()
        if not _NAME_RE.match(first_name):
            flash("First name must be 1–50 letters, spaces, hyphens, or apostrophes.", "danger")
            return redirect(url_for("admin.admin_panel", active_tab="admins"))
        if not _NAME_RE.match(last_name):
            flash("Last name must be 1–50 letters, spaces, hyphens, or apostrophes.", "danger")
            return redirect(url_for("admin.admin_panel", active_tab="admins"))
        if not _USERNAME_RE.match(username):
            flash("Username must be 3–20 alphanumeric characters or underscores.", "danger")
            return redirect(url_for("admin.admin_panel", active_tab="admins"))
    if not _EMAIL_RE.match(email):
        flash("Invalid email address.", "danger")
        return redirect(url_for("admin.admin_panel", active_tab="admins"))
    if role not in _VALID_ROLES:
        flash("Invalid role selected.", "danger")
        return redirect(url_for("admin.admin_panel", active_tab="admins"))

    if admin_service.create_admin(first_name, last_name, username, email, role):
        flash("Admin created succesfully!", "success")
        if current_app.config["ADMIN_AUTH_MODE"] == "entra":
            email_service.send_entra_welcome_email(first_name, email)
        else:
            email_service.send_welcome_email(username, first_name, email)
    else:
        flash("Failed to create admin account. Please check logs for more details", "danger")
    return redirect(url_for("admin.admin_panel", active_tab="admins"))

@admin_blueprint.route("/logout")
def logout():
    user_type = 0
    if "admin_username" in session:
        user_type = 1
    try:
        flashes = session.get('_flashes', [])
        session.clear()
        session['_flashes'] = flashes
    except Exception:
        print(traceback.format_exc())
        flash("Error: Unable to logout. Please try again later", "danger")
        if user_type:
            return redirect(url_for("admin.admin_panel"))
        return redirect(url_for("user.home"))
    if user_type:
        flash("Logged out successfully!", "success")
        return redirect(url_for("admin.admin"))
    return redirect(url_for("user.home"))

@admin_blueprint.route("/reject_submission", methods=["POST"])
@DecoratorHelper.check_admin_login
@DecoratorHelper.check_first_login
def reject_submission():
    submission_service = current_app.submission_service
    request_id = request.form.get("request_id")
    comments = request.form.get("comments", "")
    if len(comments) > _MAX_COMMENT_LEN:
        return {"success": False, "message": f"Comments must be {_MAX_COMMENT_LEN} characters or fewer."}
    if submission_service.reject_request(request_id, comments, actor=session.get("admin_username")):
        return {"success": True, "message": "Submission rejected successfully!"}
    else:
        return {"success": False, "message": "Failed to reject submission. Please check logs for more details"}

@admin_blueprint.route("/approve_submission", methods=["POST"])
@DecoratorHelper.check_admin_login
@DecoratorHelper.check_first_login
def approve_submission():
    submission_service = current_app.submission_service
    request_id = request.form.get("request_id")
    if submission_service.approve_request(request_id, actor=session.get("admin_username")):
        return {"success": True, "message": "Submission approved successfully!"}
    else:
        return {"success": False, "message": "Failed to approve submission. Please check logs for more details"}
    
@admin_blueprint.route("/change_admin_password", methods=["POST", "GET"])
@DecoratorHelper.check_admin_login
def change_admin_password():
    if current_app.config["ADMIN_AUTH_MODE"] == "entra" and "forgot_password_token" not in session:
        flash("Password management is disabled in Entra-only mode.", "danger")
        return redirect(url_for("admin.admin_panel", active_tab="profile"))
    auth_service = current_app.auth_service
    if request.method == "GET":
        if "forgot_password_token" in session:
            return render_template("change_admin_password.html", forgot_password=True)
        return render_template("change_admin_password.html")
    
    elif request.method == "POST":
        if "forgot_password_token" not in session:
            current_password = request.form.get("current_password")
            if not auth_service.compare_password(session["admin_username"], current_password):
                flash("Current password is incorrect", "danger")
                return redirect(url_for("admin.admin_panel", active_tab="profile"))
        new_password = request.form.get("new_password")
        confirm_password = request.form.get("confirm_password")
        if new_password != confirm_password:
            flash("Passwords do not match", "danger")
            return redirect(url_for("admin.change_admin_password"))
        if auth_service.update_admin_password(session["admin_username"], new_password):
            if "forgot_password_token" in session:
                auth_service.del_forgot_password_token(session["forgot_password_token"])
            session.clear()
            flash("Password changed successfully!", "success")
            return redirect(url_for("admin.admin"))
        else:
            flash("Error changing password, please try again!", "danger")
            if 'forgot_password_token' in session:
                return redirect(url_for("admin.change_admin_password"))
            return redirect(url_for('admin.admin_panel', active_tab='profile'))
        
@admin_blueprint.route("/forgot_password", methods=["POST", "GET"])
def forgot_password():
    if current_app.config["ADMIN_AUTH_MODE"] == "entra":
        flash("Password reset is not available in Entra-only mode.", "danger")
        return redirect(url_for("admin.admin"))
    email_service = current_app.email_service
    auth_service = current_app.auth_service
    if request.method == "POST":
        if not forgot_password_limiter.is_allowed(request.remote_addr):
            flash("Too many requests. Please try again later.", "danger")
            return redirect(url_for("admin.forgot_password"))
        identifier = request.form.get("identifier")
        is_email = re.match(r"^[^@]+@[^@]+\.[^@]+$", identifier)
        if is_email:
            email_service.send_forgot_password_email(**{"email": identifier})
        else:
            email_service.send_forgot_password_email(**{"username": identifier})
        flash("If your account exists, you will receive an email with instructions to reset your password.", "info")
        return redirect(url_for("admin.admin"))
    if request.method == "GET":
        if request.args.get("token"):
            token = request.args.get("token")
            username = auth_service.validate_forgot_password_token(token)
            if username:
                session.clear()
                session["admin_username"] = username
                session["forgot_password_token"] = token
                return redirect(url_for("admin.change_admin_password"))
            else:
                flash("Invalid or expired token", "danger")
                return redirect(url_for("admin.admin"))
        return render_template("admin_forgot_password.html")
    
@admin_blueprint.route("/batch_edit", methods=["POST"])
@DecoratorHelper.check_admin_login
@DecoratorHelper.check_first_login
def batch_edit():
    submission_service = current_app.submission_service
    request_ids = request.form.getlist("request_ids")
    action = request.form.get("action")
    comments = request.form.get("comments", "")
    errors = {}

    actor = session.get("admin_username")
    if action == "approve":
        for request_id in request_ids:
            if not submission_service.approve_request(request_id, actor=actor):
                errors[request_id] = "Failed to approve request"
        if errors:
            return {"success": False, "message": "Failed to approve one or more requests", "errors": errors}
        return {"success": True, "message": "All submissions approved successfully!"}
    elif action == "reject":
        if len(comments) > _MAX_COMMENT_LEN:
            return {"success": False, "message": f"Comments must be {_MAX_COMMENT_LEN} characters or fewer."}
        for request_id in request_ids:
            if not submission_service.reject_request(request_id, comments, actor=actor):
                errors[request_id] = "Failed to reject request"
        if errors:
            return {"success": False, "message": "Failed to reject one or more requests", "errors": errors}
        return {"success": True, "message": "All submissions rejected successfully!"}
    else:
        flash("Invalid action selected", "danger")
        return redirect(url_for("admin.admin_panel"))

@admin_blueprint.route("/edit_admin_account", methods=["POST"])
@DecoratorHelper.check_admin_login
@DecoratorHelper.check_first_login
def edit_admin_account():
    admin_service = current_app.admin_service
    if session["role"] != "super":
        flash("You do not have permission to edit admin accounts", "danger")
        return redirect(url_for("admin.admin_panel", active_tab="admins"))

    user_id = request.form.get("user_id", "")
    first_name = request.form.get("first_name", "").strip()
    last_name = request.form.get("last_name", "").strip()
    username = request.form.get("username", "").strip()
    email = request.form.get("email", "").strip()
    role = request.form.get("role", "").strip()

    try:
        user_id_int = int(user_id)
    except (TypeError, ValueError):
        flash("Invalid user ID.", "danger")
        return redirect(url_for("admin.admin_panel", active_tab="admins"))

    if not _NAME_RE.match(first_name):
        flash("First name must be 1–50 letters, spaces, hyphens, or apostrophes.", "danger")
        return redirect(url_for("admin.admin_panel", active_tab="admins"))
    if not _NAME_RE.match(last_name):
        flash("Last name must be 1–50 letters, spaces, hyphens, or apostrophes.", "danger")
        return redirect(url_for("admin.admin_panel", active_tab="admins"))
    if not _USERNAME_RE.match(username):
        flash("Username must be 3–20 alphanumeric characters or underscores.", "danger")
        return redirect(url_for("admin.admin_panel", active_tab="admins"))
    if not _EMAIL_RE.match(email):
        flash("Invalid email address.", "danger")
        return redirect(url_for("admin.admin_panel", active_tab="admins"))
    if role not in _VALID_ROLES:
        flash("Invalid role selected.", "danger")
        return redirect(url_for("admin.admin_panel", active_tab="admins"))

    if user_id_int == session["user_id"]:
        flash("You cannot edit your own account from here. Please use the profile page.", "danger")
        return redirect(url_for("admin.admin_panel", active_tab="profile"))

    if admin_service.edit_admin(user_id, first_name, last_name, username, email, role):
        flash("Admin account updated successfully!", "success")
        return redirect(url_for("admin.admin_panel", active_tab="admins"))
    else:
        flash("Failed to update admin account. Please check logs for more details", "danger")
        return redirect(url_for("admin.admin_panel", active_tab="admins"))
    
@admin_blueprint.route("/delete_admin_account", methods=["POST"])
@DecoratorHelper.check_admin_login
@DecoratorHelper.check_first_login
def delete_admin_account():
    admin_service = current_app.admin_service
    if session["role"] != "super":
        return {"success": False, "message": "You do not have permission to delete admin accounts"}

    user_id = request.form.get("user_id", "")
    try:
        user_id_int = int(user_id)
    except (TypeError, ValueError):
        return {"success": False, "message": "Invalid user ID."}
    if user_id_int == session["user_id"]:
        return {"success": False, "message": "You cannot delete your own account"}

    if admin_service.delete_admin(user_id):
        return {"success": True, "message": "Admin account deleted successfully!"}
    else:
        return {"success": False, "message": "Failed to delete admin account. Please check logs for more details"}
    
@admin_blueprint.route("/search_submissions", methods=["POST"])
@DecoratorHelper.check_admin_login
@DecoratorHelper.check_first_login
def search_submissions():
    if request.method == "POST":
        search_term = request.form.get("search_term")
        return redirect(url_for("admin.admin_panel", active_tab="search", search_term=search_term))

@admin_blueprint.route("/delete_submission", methods=["POST"])
@DecoratorHelper.check_admin_login
@DecoratorHelper.check_first_login
def delete_submission():
    if request.method == "POST":
        request_id = request.form.get("request_id")
        submission_service = current_app.submission_service
        if submission_service.delete(request_id, actor=session.get("admin_username")):
            return {"success": True, "message": f"Deleted submission with id: {request_id} succesfully", "errors": None}
        else:
            return {"success": False, "message": f"Failed to delete submission id: {request_id}", "errors": "err"}

@admin_blueprint.route("/uploads/<path:filename>")
@DecoratorHelper.check_admin_login
def serve_upload(filename):
    return send_from_directory(current_app.config["UPLOAD_FOLDER"], filename)
        
        

