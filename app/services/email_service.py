from flask_mail import Mail, Message
from flask import render_template, session
from factories import get_logger
import datetime
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import msal
import base64
import os

class EmailService:
    def __init__(self, db=None, app=None):
        self.mail = Mail()
        self.app = app
        self.db = db
        self.mail.init_app(app)
        self.logger = get_logger("email_service")
        
        # OAuth2 configuration
        self.use_oauth = app.config.get('MAIL_USE_OAUTH', False)
        if self.use_oauth:
            self.client_id = app.config.get('AZURE_CLIENT_ID')
            self.client_secret = app.config.get('AZURE_CLIENT_SECRET')
            self.tenant_id = app.config.get('AZURE_TENANT_ID')
            self.sender_email = app.config.get('MAIL_USERNAME')
            self.scopes = ["https://outlook.office365.com/.default"]
            self.logger.info("EmailService initialized with OAuth2")
        else:
            self.logger.info("EmailService initialized with legacy authentication")

    def _get_access_token(self):
        """Acquire OAuth2 access token"""
        try:
            authority = f"https://login.microsoftonline.com/{self.tenant_id}"
            app_msal = msal.ConfidentialClientApplication(
                self.client_id,
                authority=authority,
                client_credential=self.client_secret
            )
            
            result = app_msal.acquire_token_for_client(scopes=self.scopes)
            
            if "access_token" in result:
                return result["access_token"]
            else:
                raise Exception(f"Token acquisition failed: {result.get('error_description')}")
        except Exception as e:
            self.logger.exception("Failed to acquire OAuth2 token")
            raise

    def _send_with_oauth(self, recipients, subject, html_body):
        """Send email using OAuth2 SMTP authentication"""
        try:
            access_token = self._get_access_token()
            
            msg = MIMEMultipart('alternative')
            msg['From'] = self.sender_email
            msg['To'] = ', '.join(recipients) if isinstance(recipients, list) else recipients
            msg['Subject'] = subject
            msg.attach(MIMEText(html_body, 'html'))
            
            # Connect to Microsoft 365 SMTP
            server = smtplib.SMTP('smtp.office365.com', 587)
            server.starttls()
            
            # OAuth2 authentication
            auth_string = f"user={self.sender_email}\x01auth=Bearer {access_token}\x01\x01"
            auth_b64 = base64.b64encode(auth_string.encode()).decode()
            server.docmd('AUTH', 'XOAUTH2 ' + auth_b64)
            
            server.send_message(msg)
            server.quit()
            
            return True
        except Exception as e:
            self.logger.exception("OAuth2 email send failed")
            raise

    def _send_message(self, msg):
        """Send a single message using configured method"""
        if self.use_oauth:
            return self._send_with_oauth(msg.recipients, msg.subject, msg.html)
        else:
            # Legacy flask-mail method
            with self.mail.connect() as conn:
                conn.send(msg)
            return True

    def _send_messages(self, messages):
        """Send multiple messages using configured method"""
        if self.use_oauth:
            for msg in messages:
                self._send_with_oauth(msg.recipients, msg.subject, msg.html)
        else:
            # Legacy flask-mail batch method
            with self.mail.connect() as conn:
                for msg in messages:
                    conn.send(msg)

    def send_email_alert(self) -> bool:
        messages = []
        request_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        html_body = render_template('email/admin_email.html',
                                    subject=f"{session['cn']} has requested an ID!",
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
            self._send_messages(messages)
        except Exception:
            self.logger.exception("An error occurred while trying to send an email alert!")
            return False
        
        self.logger.info(f"Successfully sent email alert to: {self.app.config['MAIL_DEFAULT_RECIP']}, {session['Email']}")
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
            self._send_message(msg)
        except Exception:
            self.logger.exception("Error occurred while trying to send the welcome email!")
            return False
        self.logger.info(f"Successfully sent welcome email to {email}")
        return True
    
    def send_forgot_password_email(self, **kwargs) -> bool:
        auth_service = self.app.auth_service
        if "email" in kwargs:
            row = self.db.execute_query("select first_name || ' ' || last_name, username, email, id from admins where email=%s", (kwargs["email"],), fetch_one=True)
        else:
            row = self.db.execute_query("select first_name || ' ' || last_name, username, email, id from admins where username=%s", (kwargs["username"],), fetch_one=True)
        if not row:
            self.logger.error("Error occurred while trying to send forgot password email")
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
            self._send_message(msg)
        except Exception:
            self.logger.exception("Error occurred while trying to send forgot password email!")
            return False
        self.logger.info(f"Successfully sent forgot password email to {kwargs}")
        return True
    
    def send_approved_email(self, request_id) -> bool:
        row = self.db.execute_query("select first_name || ' ' || last_name, email from submissions where request_id=%s", (request_id,), fetch_one=True)
        if not row:
            self.logger.error(f"Error sending approved email for request: {request_id}, row not found in db.")
            return False
        
        name = row[0]
        email = row[1]

        html_body = render_template("email/approved_submission.html", student_name=name)
        msg = Message(subject="Your ID submission has been approved!", recipients=[email], html=html_body)

        try:
            self._send_message(msg)
        except Exception:
            self.logger.exception("An email error has occurred!")
            return False
        self.logger.info(f"Submission notification successfully sent to {email}")
        return True
    
    def send_rejection_email(self, request_id, comments):
        row = self.db.execute_query("select first_name || ' ' || last_name, email from submissions where request_id=%s", (request_id,), fetch_one=True)
        if not row:
            self.logger.error(f"Error sending reject email for request: {request_id}, row not found in db.")
            return False
        
        name = row[0]
        email = row[1]

        html_body = render_template("email/reject_submission.html", student_name=name, REJECTION_COMMENTS=comments)
        msg = Message(subject="Your ID submission has been rejected!", recipients=[email], html=html_body)

        try:
            self._send_message(msg)
        except Exception:
            self.logger.exception("An email error has occurred!")
            return False
        self.logger.info(f"Submission notification successfully sent to {email}")
        return True