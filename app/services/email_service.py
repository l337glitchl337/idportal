from flask_mail import Mail, Message
from flask import render_template, session
from factories import get_logger
import datetime

class EmailService:
    def __init__(self, db=None, app=None):
        self.mail = Mail()
        self.app = app
        self.db = db
        self.mail.init_app(app)
        self.logger = get_logger("email_service")
        self.logger.info("EmailService initialized")

    def send_email_alert(self) -> bool:
        messages = []
        request_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        html_body = render_template('email/admin_email.html',
                                    subject=f"{session["cn"]} has requested an ID!",
                                    student_name=session["cn"],
                                    student_id=session["ID Number"],
                                    campus=session["Location"],
                                    request_time=request_time)
        admin_msg = Message(
            subject="New ID request!",
            recipients=[self.app.config["MAIL_DEFAULT_RECIP"]],
            html=html_body)
        
        html_body = render_template('email/student_email.html',
                                    subject=f"We have received your ID request!",
                                    student_name=session["cn"],
                                    current_year="2025",
                                    request_id=session["request_id"])
        student_msg = Message(
            subject="Thank you for submitting your request.",
            recipients=[session["Email"]],
            html=html_body)
        
        messages.append(admin_msg)
        messages.append(student_msg)
        
        try:
            with self.mail.connect() as conn:
                for msg in messages:
                    conn.send(msg)
        except Exception:
            self.logger.exception("An error occurred while trying to send an email alert!")
            return False
        
        self.logger.info(f"Succesfully sent email alert to: {self.app.config["MAIL_DEFAULT_RECIP"]}, {session["Email"]}")
        return True
    
    def send_welcome_email(self, username, password, first_name, email) -> bool:
        html_body = render_template('email/admin_welcome.html',
                                    username=username,
                                    password=password,
                                    first_name=first_name)
        msg = Message(subject="Welcome to IDPortal!",
                    recipients=[email],
                    html=html_body)
        try:
            with self.mail.connect() as conn:
                conn.send(msg)
        except Exception:
            self.logger.exception("Error occurred while trying to send the welcome email!")
            return False
        self.logger.info(f"Succesfully sent welcome email to {email}")
        return True
    
    def send_forgot_password_email(self, **kwargs) -> bool:
        auth_service = self.app.auth_service
        if "email" in kwargs:
            row = self.db.execute_query("select first_name || ' ' || last_name, username, email, id from admins where email=%s", (kwargs["email"],), fetch_one=True)
        else:
            row = self.db.execute_query("select first_name || ' ' || last_name, username, email, id from admins where username=%s", (kwargs["username"],), fetch_one=True)
        if not row:
            self.logger.error("Error occured while trying to send forgot password email")
            self.logger.error(f"Unable to find record for {kwargs}")
            return False
        
        email = row[2]
        full_name = row[0]
        username = row[1]
        user_id = row[3]
        url, token = auth_service.gen_random_forgot_password_link()

        result = self.db.execute_query("insert into admin_forgot_password (user_id, token) values (%s, %s)", (user_id, token))
        if not result:
            return False

        html_body = render_template('email/forgot_password.html',
                                    full_name=full_name,
                                    username=username,
                                    url=url)
        msg = Message(subject="Forgot Password Request",
                        recipients=[email],
                        html=html_body)
        try:
            with self.mail.connect() as conn:
                conn.send(msg)
        except Exception:
            self.logger.exception("Error occured while trying to send forgot password email!")
            return False
        self.logger.info(f"Succesfully sent forgot password email to {kwargs}")
        return True
    
    def send_approved_email(self, request_id) -> bool:
        row = self.db.execute_query("select first_name || ' ' || last_name, email from submissions where request_id=%s", (request_id,), fetch_one=True)
        if not row:
            self.logging.error(f"Error sending approved email for request: {request_id}, row not found in db.")
            return False
        
        name = row[0]
        email = row[1]

        html_body = render_template("email/approved_submission.html", student_name=name)
        msg = Message(subject="Your ID submission has been approved!", recipients=[email], html=html_body)

        try:
            with self.mail.connect() as conn:
                conn.send(msg)
        except Exception:
            self.logger.exception("An email error has occurred!")
            return False
        self.logger.info(f"Submission notification succesfully sent to {email}")
        return True
    
    def send_rejection_email(self, request_id, comments):
        row = self.db.execute_query("select first_name || ' ' || last_name, email from submissions where request_id=%s", (request_id,), fetch_one=True)
        if not row:
            self.logging.error(f"Error sending reject email for request: {request_id}, row not found in db.")
            return False
        
        name = row[0]
        email = row[1]

        html_body = render_template("email/reject_submission.html", student_name=name, REJECTION_COMMENTS=comments)
        msg = Message(subject="Your ID submission has been rejected!", recipients=[email], html=html_body)

        try:
            with self.mail.connect() as conn:
                conn.send(msg)
        except Exception:
            self.logger.exception("An email error has occurred!")
            return False
        self.logger.info(f"Submission notification succesfully sent to {email}")
        return True