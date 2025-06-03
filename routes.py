from flask import render_template, request, redirect, url_for, flash, Blueprint, current_app, session
from functions import *
from ldap_functions import *
import os
import traceback
import re

blueprint = Blueprint("main", __name__)

@blueprint.route("/")
def home():
    return render_template("login.html")

@blueprint.route("/login", methods=["POST"])
def login():
    ldap_auth = Ldap_Auth()

    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")

        attrs, result = ldap_auth.auth_user(email, password)

        if result:
            set_session_attrs(attrs)
            return redirect(url_for('main.landing'))
        else:
            flash("Error: Please check email/password", "danger")
            return redirect(url_for("main.home"))

@blueprint.route("/landing", methods=["GET"])
@check_login
def landing():
    return render_template("landing.html", 
                           first_name=session["first_name"][0].decode(), 
                           last_name=session["last_name"][0].decode(), 
                           student_id=session["student_id"][0].decode(), 
                           campus=session["campus"][0].decode()
                           )

@blueprint.route("/upload_form")
@check_login
def upload_form():
    return render_template("upload_photo.html")
    
@blueprint.route("/upload_photo", methods = ["GET", "POST"])
@check_login
def upload_photo():
    if "photo" in request.files and "drivers_license" in request.files:
        photo = request.files["photo"]
        drivers_license = request.files["drivers_license"]
        if photo.filename == '' or drivers_license.filename == '':
            flash("Error", "danger")
            return redirect(url_for("main.home"))
        if photo and drivers_license:
            pfn = generate_unique_filename(photo.filename)
            lfn = generate_unique_filename(drivers_license.filename)


            photo.save(os.path.join(current_app.config["UPLOAD_FOLDER"], pfn))
            drivers_license.save(os.path.join(current_app.config["UPLOAD_FOLDER"], lfn))

            if(create_submission(pfn, lfn)):
                flash("Documents uploaded successfully!", "success")
                flash("You will receive an email once your ID is ready!", "success")

                send_email_alert()
                return redirect(url_for("main.logout"))
            else:
                flash("An error has occurred, please try again later", "danger")
                return redirect(url_for("main.logout"))
        
@blueprint.route("/admin", methods = ["POST", "GET"])
def admin():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        if admin_login(username, password):
            if session["on_login"]:
                flash("Please change your password before proceeding", "danger")
                return redirect(url_for("main.change_admin_password"))
            return redirect(url_for("main.admin_panel"))
        else:
            flash("Invalid username/password combination", "danger")
            return redirect(url_for("main.admin"))
    return render_template("admin.html")

@blueprint.route("/admin_panel")
@check_admin_login
@check_first_login
def admin_panel():
    page = request.args.get("page", 1, type=int)

    active_tab = request.args.get("active_tab", "pending") 
    current_user = {"username": session["admin_username"], "role": session["role"], "email": session["email"], "user_id": session["user_id"]}
    data = populate_admin_panel(page)
    return render_template("admin_panel.html", **data, active_tab=active_tab, current_user=current_user, current_page=page)

@blueprint.route("/create_admin_account", methods = ["POST"])
@check_admin_login
@check_first_login
def create_admin_account():
    first_name = request.form.get("first_name")
    last_name = request.form.get("last_name")
    username = request.form.get("username")
    password = request.form.get("password")
    email = request.form.get("email")
    role = request.form.get("role")

    if create_admin(first_name, last_name, username, password, email, role):
        flash("Admin created succesfully!", "success")
        send_welcome_email(username, password, first_name, email)
    else:
        flash("Failed to create admin account. Please check logs for more details", "danger")
    return redirect(url_for("main.admin_panel", active_tab="admins"))

@blueprint.route("/logout")
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
            return redirect(url_for("main.admin_panel"))
        return redirect(url_for("main.home"))
    if user_type:
        flash("Logged out successfully!", "success")
        return redirect(url_for("main.admin"))
    return redirect(url_for("main.home"))

@blueprint.route("/reject_submissiion", methods=["POST"])
@check_admin_login
@check_first_login
def reject_submission():
    request_id = request.form.get("request_id")
    comments = request.form.get("comments")
    if reject_request(request_id, comments):
        return {"success": True, "message": "Submission rejected successfully!"}
    else:
        return {"success": False, "message": "Failed to reject submission. Please check logs for more details"}

@blueprint.route("/approve_submission", methods=["POST"])
@check_admin_login
@check_first_login
def approve_submission():
    request_id = request.form.get("request_id")
    if approve_request(request_id):
        return {"success": True, "message": "Submission approved successfully!"}
    else:
        return {"success": False, "message": "Failed to approve submission. Please check logs for more details"}
    
@blueprint.route("/change_admin_password", methods=["POST", "GET"])
@check_admin_login
def change_admin_password():
    if request.method == "GET":
        if "forgot_password_token" in session:
            return render_template("change_admin_password.html", forgot_password=True)
        return render_template("change_admin_password.html")
    
    elif request.method == "POST":
        if "forgot_password_token" not in session:
            current_password = request.form.get("current_password")
            if not compare_password(session["admin_username"], current_password):
                flash("Current password is incorrect", "danger")
                return redirect(url_for("main.admin_panel", active_tab="profile"))
        new_password = request.form.get("new_password")
        confirm_password = request.form.get("confirm_password")
        if new_password != confirm_password:
            flash("Passwords do not match", "danger")
            return redirect(url_for("main.change_admin_password"))
        if update_admin_password(session["admin_username"], new_password):
            if "forgot_password_token" in session:
                del_forgot_password_token(session["forgot_password_token"])
            session.clear()
            flash("Password changed successfully!", "success")
            return redirect(url_for("main.admin"))
        else:
            flash("Error changing password, please try again!", "danger")
            return redirect(url_for("main.change_admin_password"))
        
@blueprint.route("/forgot_password", methods=["POST", "GET"])
def forgot_password():
    if request.method == "POST":
        identifier = request.form.get("identifier")
        is_email = re.match(r"^[^@]+@[^@]+\.[^@]+$", identifier)
        if is_email:
            send_forgot_password_email(**{"email": identifier})
        else:
            send_forgot_password_email(**{"username": identifier})
        flash("If your account exists, you will receive an email with instructions to reset your password.", "info")
        return redirect(url_for("main.admin"))
    if request.method == "GET":
        if request.args.get("token"):
            token = request.args.get("token")
            username = validate_forgot_password_token(token)
            if username:
                session["admin_username"] = username
                session["forgot_password_token"] = token
                return redirect(url_for("main.change_admin_password"))
            else:
                flash("Invalid or expired token", "danger")
                return redirect(url_for("main.admin"))
        return render_template("admin_forgot_password.html")
    
@blueprint.route("/batch_edit", methods=["POST"])
@check_admin_login
@check_first_login
def batch_edit():
    request_ids = request.form.getlist("request_ids")
    action = request.form.get("action")
    comments = request.form.get("comments", "")
    errors = {}

    if action == "approve":
        for request_id in request_ids:
            if not approve_request(request_id):
                errors[request_id] = "Failed to approve request"
        if errors:
            return {"success": False, "message": "Failed to approve one or more requests", "errors": errors}
        return {"success": True, "message": "All submissions approved successfully!"}
    elif action == "reject":
        for request_id in request_ids:
            if not reject_request(request_id, comments):
                errors[request_id] = "Failed to reject request"
        if errors:
            return {"success": False, "message": "Failed to reject one or more requests", "errors": errors}
        return {"success": True, "message": "All submissions rejected successfully!"}
    else:
        flash("Invalid action selected", "danger")
        return redirect(url_for("main.admin_panel"))

@blueprint.route("/edit_admin_account", methods=["POST"])
@check_admin_login
@check_first_login
def edit_admin_account():
    if session["role"] != "super":
        flash("You do not have permission to edit admin accounts", "danger")
        return redirect(url_for("main.admin_panel", active_tab="admins"))
    user_id = request.form.get("user_id")
    first_name = request.form.get("first_name")
    last_name = request.form.get("last_name")
    username = request.form.get("username")
    email = request.form.get("email")
    role = request.form.get("role")

    if user_id == session["user_id"]:
        flash("You cannot edit your own account from here. Please use the profile page.", "danger")
        return redirect(url_for("main.admin_panel", active_tab="profile"))

    if edit_admin(user_id, first_name, last_name, username, email, role):
        flash("Admin account updated successfully!", "success")
        return redirect(url_for("main.admin_panel", active_tab="admins"))
    else:
        flash("Failed to update admin account. Please check logs for more details", "danger")
        return redirect(url_for("main.admin_panel", active_tab="admins"))
    
@blueprint.route("/delete_admin_account", methods=["POST"])
@check_admin_login
@check_first_login
def delete_admin_account():
    if session["role"] != "super":
        return {"success": False, "message": "You do not have permission to delete admin accounts"}
    
    user_id = request.form.get("user_id")
    if user_id == session["user_id"]:
        return {"success": False, "message": "You cannot delete your own account"}

    if delete_admin(user_id):
        return {"success": True, "message": "Admin account deleted successfully!"}
    else:
        return {"success": False, "message": "Failed to delete admin account. Please check logs for more details"}