from flask import render_template, request, redirect, url_for, flash, Blueprint, current_app, session
from functions import *
from ldap_functions import *
from flask_mail import Message
from extensions import mail
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
    current_user = {"username": session["admin_username"], "role": session["role"], "email": session["email"]}
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
    return redirect(url_for("main.admin_panel"))

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
    print(request_id)
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
        return render_template("change_admin_password.html")
    elif request.method == "POST":
        current_password = request.form.get("current_password")
        if not compare_password(session["admin_username"], current_password):
            flash("Current password is incorrect", "danger")
            return redirect(url_for("main.change_admin_password"))
        new_password = request.form.get("new_password")
        confirm_password = request.form.get("confirm_password")
        if new_password != confirm_password:
            flash("Passwords do not match", "danger")
            return redirect(url_for("main.change_admin_password"))
        if update_admin_password(session["admin_username"], new_password):
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
        print(identifier)
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
            if validate_forgot_password_token(token):
                return redirect(url_for("main.reset_password", token=token))
            else:
                flash("Invalid or expired token", "danger")
                return redirect(url_for("main.admin"))
        return render_template("admin_forgot_password.html")