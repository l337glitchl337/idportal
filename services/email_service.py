from flask_mail import Mail, Message
from flask import render_template, session
import datetime
import traceback

class EmailService:
    def __init__(self, db=None, app=None):
        self.mail = Mail()
        self.app = app
        self.db = db
        self.mail.init_app(app)

    def send_email_alert(self) -> bool:
        messages = []
        request_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        html_body = render_template('email/admin_email.html',
                                    subject=f"{session["cn"][0].decode()} has requested an ID!",
                                    student_name=session["cn"][0].decode(),
                                    student_id=session["student_id"][0].decode(),
                                    campus=session["campus"][0].decode(),
                                    request_time=request_time)
        admin_msg = Message(
            subject="New ID request!",
            recipients=[self.app.config["MAIL_DEFAULT_RECIP"]],
            html=html_body)
        
        html_body = render_template('email/student_email.html',
                                    subject=f"We have received your ID request!",
                                    student_name=session["cn"][0].decode(),
                                    current_year="2025",
                                    request_id="123456")
        student_msg = Message(
            subject="Thank you for submitting your request.",
            recipients=[session["mail"][0].decode()],
            html=html_body)
        
        messages.append(admin_msg)
        messages.append(student_msg)
        
        try:
            with self.mail.connect() as conn:
                for msg in messages:
                    conn.send(msg)
        except:
            print("*******************")
            print("Error sending email")
            print("*******************")
            print(traceback.format_exc())
            return False

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
        except: 
            print("*******************")
            print("Error sending email")
            print("*******************")
            print(traceback.format_exc())
            return False
        return True
    
    def send_forgot_password_email(self, **kwargs) -> bool:
        auth_service = self.app.auth_service
        if "email" in kwargs:
            row = self.db.execute_query("select first_name || ' ' || last_name, username, email, id from admins where email=%s", (kwargs["email"],), fetch_one=True)
        else:
            row = self.db.execute_query("select first_name || ' ' || last_name, username, email, id from admins where username=%s", (kwargs["username"],), fetch_one=True)
        if not row:
            print("No user found with the provided email or username.")
            return False
        
        email = row[2]
        full_name = row[0]
        username = row[1]
        user_id = row[3]
        url, token = auth_service.gen_random_forgot_password_link()

        result = self.db.execute_query("insert into admin_forgot_password (user_id, token) values (%s, %s)", (user_id, token))
        if not result:
            print("Failed to insert forgot password token into the database.")
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
        except:
            print("*******************")
            print("Error sending email")
            print("*******************")
            print(traceback.format_exc())
            return False
        return True