from flask import render_template, request, redirect, url_for, flash, Blueprint, current_app, session
from helpers import DecoratorHelper, UtilityHelper
import os

user_blueprint = Blueprint("user", __name__)

@user_blueprint.route("/")
def home():
    return render_template("login.html")

@user_blueprint.route("/login", methods=["POST"])
def login():
    ldap_service = current_app.ldap_service
    auth_service = current_app.auth_service
    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")

        message, attrs, result = ldap_service.auth_user(email, password)

        if result:
            auth_service.set_session_attrs(attrs)
            return redirect(url_for('user.landing'))
        else:
            if not message:
                flash("Error: Please check email/password", "danger")
            else:
                flash(message, "info")
        
            return redirect(url_for("user.home"))

@user_blueprint.route("/landing", methods=["GET"])
@DecoratorHelper.check_login
def landing():
    return render_template("landing.html", attrs=session['attrs'])

@user_blueprint.route("/upload_form")
@DecoratorHelper.check_login
def upload_form():
    return render_template("upload_photo.html")
    
@user_blueprint.route("/upload_photo", methods = ["GET", "POST"])
@DecoratorHelper.check_login
def upload_photo():
    submission_service = current_app.submission_service
    email_service = current_app.email_service
    if "photo" in request.files and "drivers_license" in request.files:
        photo = request.files["photo"]
        drivers_license = request.files["drivers_license"]
        if photo.filename == '' or drivers_license.filename == '':
            flash("Error", "danger")
            return redirect(url_for("user.home"))
        if photo and drivers_license:
            pfn = UtilityHelper.generate_unique_filename(photo.filename)
            lfn = UtilityHelper.generate_unique_filename(drivers_license.filename)


            photo.save(os.path.join(current_app.config["UPLOAD_FOLDER"], pfn))
            drivers_license.save(os.path.join(current_app.config["UPLOAD_FOLDER"], lfn))

            if(submission_service.create_submission(pfn, lfn)):
                flash("Documents uploaded successfully!", "success")
                flash("You will receive an email once your ID is ready!", "success")

                email_service.send_email_alert()
                return redirect(url_for("admin.logout"))
            else:
                flash("An error has occurred, please try again later", "danger")
                return redirect(url_for("admin.logout"))