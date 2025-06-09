from flask import render_template, request, redirect, url_for, flash, Blueprint, current_app, session
from helpers import DecoratorHelper, UtilityHelper
import traceback
import re
import os

admin_blueprint = Blueprint("admin", __name__)

@admin_blueprint.route("/admin", methods = ["POST", "GET"])
def admin():
    if request.method == "POST":
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
    page = request.args.get("page", 1, type=int)

    active_tab = request.args.get("active_tab", "pending") 
    current_user = {"username": session["admin_username"], "role": session["role"], "email": session["email"], "user_id": session["user_id"]}
    data = admin_service.populate_admin_panel(page, active_tab=active_tab)
    return render_template("admin_panel.html", **data, active_tab=active_tab, current_user=current_user, current_page=page)

@admin_blueprint.route("/create_admin_account", methods = ["POST"])
@DecoratorHelper.check_admin_login
@DecoratorHelper.check_first_login
def create_admin_account():
    admin_service = current_app.admin_service
    email_service = current_app.email_service
    first_name = request.form.get("first_name")
    last_name = request.form.get("last_name")
    username = request.form.get("username")
    password = request.form.get("password")
    email = request.form.get("email")
    role = request.form.get("role")

    if admin_service.create_admin(first_name, last_name, username, password, email, role):
        flash("Admin created succesfully!", "success")
        email_service.send_welcome_email(username, password, first_name, email)
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

@admin_blueprint.route("/reject_submissiion", methods=["POST"])
@DecoratorHelper.check_admin_login
@DecoratorHelper.check_first_login
def reject_submission():
    submission_service = current_app.submission_service
    request_id = request.form.get("request_id")
    comments = request.form.get("comments")
    
    if submission_service.reject_request(request_id, comments):
        return {"success": True, "message": "Submission rejected successfully!"}
    else:
        return {"success": False, "message": "Failed to reject submission. Please check logs for more details"}

@admin_blueprint.route("/approve_submission", methods=["POST"])
@DecoratorHelper.check_admin_login
@DecoratorHelper.check_first_login
def approve_submission():
    submission_service = current_app.submission_service
    request_id = request.form.get("request_id")
    if submission_service.approve_request(request_id):
        return {"success": True, "message": "Submission approved successfully!"}
    else:
        return {"success": False, "message": "Failed to approve submission. Please check logs for more details"}
    
@admin_blueprint.route("/change_admin_password", methods=["POST", "GET"])
@DecoratorHelper.check_admin_login
def change_admin_password():
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
            return redirect(url_for("admin.change_admin_password"))
        
@admin_blueprint.route("/forgot_password", methods=["POST", "GET"])
def forgot_password():
    email_service = current_app.email_service
    auth_service = current_app.auth_service
    if request.method == "POST":
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

    if action == "approve":
        for request_id in request_ids:
            if not submission_service.approve_request(request_id):
                errors[request_id] = "Failed to approve request"
        if errors:
            return {"success": False, "message": "Failed to approve one or more requests", "errors": errors}
        return {"success": True, "message": "All submissions approved successfully!"}
    elif action == "reject":
        for request_id in request_ids:
            if not submission_service.reject_request(request_id, comments):
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
    user_id = request.form.get("user_id")
    first_name = request.form.get("first_name")
    last_name = request.form.get("last_name")
    username = request.form.get("username")
    email = request.form.get("email")
    role = request.form.get("role")

    if user_id == session["user_id"]:
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
    
    user_id = request.form.get("user_id")
    if user_id == session["user_id"]:
        return {"success": False, "message": "You cannot delete your own account"}

    if admin_service.delete_admin(user_id):
        return {"success": True, "message": "Admin account deleted successfully!"}
    else:
        return {"success": False, "message": "Failed to delete admin account. Please check logs for more details"}