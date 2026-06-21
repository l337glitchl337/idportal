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

    def _send(self, subject, recipients, template, **ctx) -> bool:
        html_body = render_template(template, **ctx)
        msg = Message(subject=subject, recipients=recipients, html=html_body)
        try:
            with self.mail.connect() as conn:
                conn.send(msg)
        except Exception:
            self.logger.exception(f"Error sending '{subject}' to {recipients}")
            return False
        self.logger.info(f"Sent '{subject}' to {recipients}")
        return True

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
                                    current_year=str(datetime.datetime.now().year),
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
    
    def send_welcome_email(self, username, first_name, email) -> bool:
        auth_service = self.app.auth_service
        row = self.db.execute_query("select id from admins where username=%s", (username,), fetch_one=True)
        if not row:
            self.logger.error(f"Could not find admin {username} to send welcome email.")
            return False
        user_id = row[0]
        url, token = auth_service.gen_random_forgot_password_link()
        result = self.db.execute_query(
            "insert into admin_forgot_password (user_id, token, expire_after) values (%s, %s, now() + interval '24 hours')",
            (user_id, auth_service._hash_token(token))
        )
        if not result:
            self.logger.error(f"Could not insert setup token for new admin {username}.")
            return False
        return self._send("Welcome to IDPortal!", [email], 'email/admin_welcome.html',
                          username=username, first_name=first_name, url=url)
    
    def send_entra_welcome_email(self, first_name, email) -> bool:
        return self._send("Welcome to IDPortal!", [email], 'email/admin_welcome_entra.html', first_name=first_name)

    def send_forgot_password_email(self, **kwargs) -> bool:
        auth_service = self.app.auth_service
        if "email" in kwargs:
            row = self.db.execute_query("select first_name || ' ' || last_name, username, email, id from admins where email=%s", (kwargs["email"],), fetch_one=True)
        else:
            row = self.db.execute_query("select first_name || ' ' || last_name, username, email, id from admins where username=%s", (kwargs["username"],), fetch_one=True)
        # Always generate a token regardless of whether user exists to normalise response time
        _, _ = auth_service.gen_random_forgot_password_link()
        if not row:
            self.logger.warning(f"Forgot password requested for unknown identifier: {kwargs}")
            return False
        
        email = row[2]
        full_name = row[0]
        username = row[1]
        user_id = row[3]
        url, token = auth_service.gen_random_forgot_password_link()

        result = self.db.execute_query("insert into admin_forgot_password (user_id, token) values (%s, %s)", (user_id, auth_service._hash_token(token)))
        if not result:
            return False

        return self._send("Forgot Password Request", [email], 'email/forgot_password.html',
                          full_name=full_name, username=username, url=url)
    
    def send_approved_email(self, request_id) -> bool:
        row = self.db.execute_query("select first_name || ' ' || last_name, email from submissions where request_id=%s", (request_id,), fetch_one=True)
        if not row:
            self.logger.error(f"Error sending approved email for request: {request_id}, row not found in db.")
            return False
        
        name = row[0]
        email = row[1]

        return self._send("Your ID submission has been approved!", [email],
                          "email/approved_submission.html", student_name=name)
    
    def send_rejection_email(self, request_id, comments):
        row = self.db.execute_query("select first_name || ' ' || last_name, email from submissions where request_id=%s", (request_id,), fetch_one=True)
        if not row:
            self.logger.error(f"Error sending reject email for request: {request_id}, row not found in db.")
            return False
        
        name = row[0]
        email = row[1]

        return self._send("Your ID submission has been rejected!", [email],
                          "email/reject_submission.html", student_name=name, REJECTION_COMMENTS=comments)