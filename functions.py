from werkzeug.utils import secure_filename
from uuid import uuid4
from flask import session, redirect, url_for, flash, current_app, render_template
from functools import wraps
from extensions import mail
from flask_mail import Message
import bcrypt
import psycopg2
import traceback
import datetime
import os

def generate_unique_filename(filename : str) -> str:
    filename = secure_filename(filename)
    _, extension = os.path.splitext(filename)
    return f"{uuid4()}{extension}"

def get_db_params() -> dict:
    params = {
        "dbname" : current_app.config["PG_DBNAME"],
        "user" : current_app.config["PG_USER"],
        "password" : current_app.config["PG_PWD"],
        "host" : current_app.config["PG_HOST"],
        "port" : current_app.config["PG_PORT"]
    }
    return params

def check_login(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'username' not in session:
            flash("Please login first", "danger")
            return redirect(url_for("main.home"))
        return f(*args, **kwargs)
    return decorated

def check_admin_login(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'admin_username' not in session:
            flash("Please login first", "danger")
            return redirect(url_for("main.admin"))
        return f(*args, **kwargs)
    return decorated

def check_first_login(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if session["on_login"] == 1:
            flash("Please change your password first!", "danger")
            return redirect(url_for("main.first_login"))
        return f(*args, **kwargs)
    return decorated

def set_session_attrs(attrs) -> bool:
    try:
        session["username"] = attrs["dn"]
        session["first_name"] = attrs["givenName"]
        session["last_name"] = attrs["sn"]
        session["student_id"] = attrs["title"]
        session["campus"] = attrs["o"]
        session["cn"] = attrs["cn"]
        session["mail"] = attrs["mail"]
        return True
    except:
        return False
    
def send_email_alert() -> bool:
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
        recipients=[current_app.config["MAIL_DEFAULT_RECIP"]],
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
        with mail.connect() as conn:
            for msg in messages:
                conn.send(msg)
    except:
        print("*******************")
        print("Error sending email")
        print("*******************")
        print(traceback.format_exc())
        return False

    return True

def send_welcome_email(username, password, first_name, email) -> bool:
    html_body = render_template('email/admin_welcome.html',
                                username=username,
                                password=password,
                                first_name=first_name)
    msg = Message(subject="Welcome to IDPortal!",
                  recipients=[email],
                  html=html_body)
    try:
        with mail.connect() as conn:
            conn.send(msg)
    except: 
        print("*******************")
        print("Error sending email")
        print("*******************")
        print(traceback.format_exc())
        return False
    return True

def check_bfa(email, ip_address, failed) -> bool:
    err = 0
    params = get_db_params()

    try:
        conn = psycopg2.connect(**params)
        cursor = conn.cursor()
        cursor.execute(f"select * from bfa where email='{email}'")
        row = cursor.fetchone()

        if row:
            if int(row[3]) < 3 and failed:
                cursor.execute(f"""
                               update bfa set failed_attempts=failed_attempts+1,
                               timestamp_inserted=now()
                               where email='{email}'"""
                               )
            elif int(row[3]) >= 3 and not failed:
                cursor.execute(f"""select (now() - timestamp_inserted) >
                                interval '30 minutes' as is_older
                                from bfa
                                where email='{email}'""")
                row = cursor.fetchone()
                if not bool(row[0]):
                    cursor.execute(f"select timestamp_inserted + interval '30 minutes' from bfa where email='{email}'")
                    row = cursor.fetchone()
                    cursor.close()
                    conn.close()
                    print(f"""IP: {ip_address} has failed to login into '{email}' 3 times, \
account is locked out until {row[0]} authentication will not be tried until lockout has expired.""")
                    return False
                else:
                    cursor.execute(f"delete from bfa where email='{email}'")
                    conn.commit()
                    cursor.close()
                    conn.close()
                    return True
        elif not row and failed:
            cursor.execute(f"""
                           insert into bfa (email, ip_address)
                           values ('{email}', '{ip_address}'::inet)"""
                           )
        conn.commit()
        cursor.close()
        conn.close()
    except:
        print("***************************")
        print("Error - Postgres SQL Error.")
        print("***************************")
        print(traceback.format_exc())
        err = 1
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()
    
    if err:
        return False
    else:
        return True
    
def admin_login(email, password) -> bool:
    params = get_db_params()

    try:
        conn = psycopg2.connect(**params)
        cursor = conn.cursor()
        cursor.execute("select first_name, last_name, username, email, password, status, role, on_login from admins where username=%s", (email,))
        row = cursor.fetchone()

        if not row:
            return False
        
        db_password = row[4]
        if not bcrypt.checkpw(password.encode("utf-8"), db_password.encode("utf-8")):
            return False
        session["first_name"] = row[0]
        session["last_name"] = row[1]
        session["admin_username"] = row[2]
        session["email"] = row[3]
        session["role"] = row[6]
        session["on_login"] = row[7]
    except:
        print(traceback.format_exc())
        if cursor:
            cursor.close()
        if conn:
            conn.close()
        return False
    
    return True
    
def create_admin(first_name, last_name, username, password, email, role) -> bool:
    params = get_db_params()

    password = password.encode('utf-8')
    salt = bcrypt.gensalt()
    hashed_password = bcrypt.hashpw(password, salt).decode("utf-8")

    try:
        conn = psycopg2.connect(**params)
        cursor = conn.cursor()
        cursor.execute(f"""
                    insert into admins
                    (first_name, last_name, username, password, email, role)
                    values (%s, %s, %s, %s, %s, %s)""", (first_name, last_name, username, hashed_password, email, role))
        conn.commit()
    except:
        print(traceback.format_exc())
        if cursor:
            cursor.close()
        if conn:
            conn.close()
        return False
    
    return True

def populate_admin_panel(page=1, per_page=15) -> dict:
    params = get_db_params()
    admins = []
    pending_requests = []
    approved_requests = []
    rejected_requests = []
    offset = (page - 1) * per_page

    try:
        conn = psycopg2.connect(**params)
        cursor = conn.cursor()

        cursor.execute("SELECT COUNT(*) FROM admins")
        total_admins = cursor.fetchone()[0]
        admin_pages = (total_admins + per_page - 1) // per_page
        admin_prev_page = page - 1 if page > 1 else None
        admin_next_page = page + 1 if page < admin_pages else None

        if session["role"] == "super":
            cursor.execute("select first_name || ' ' || last_name as full_name, email, username, role, id from admins order by id limit %s offset %s", (per_page, offset))
            rows = cursor.fetchall()

            for row in rows:
                d = {} 
                d["full_name"] = row[0]
                d["email"] = row[1]
                d["username"] = row[2]
                d["role"] = row[3]
                admins.append(d)

        cursor.execute("select count(*) from submissions where status='N'")
        total_pending = cursor.fetchone()[0]
        pending_pages = (total_pending + per_page - 1) // per_page
        pending_previous_page = page - 1 if page > 1 else None
        pending_next_page = page + 1 if page < pending_pages else None
        
        cursor.execute("""select first_name || ' ' || last_name as full_name, email, student_id, campus, 
                    to_char(timestamp_inserted, 'yyyy-mm-dd hh12:mi:ss AM') as timestamp_inserted,
                    photo_filepath, license_filepath, request_id
                    from submissions where status='N' order by request_id limit %s offset %s""", (per_page, offset))
        rows = cursor.fetchall()

        for row in rows:
            d = {}
            d["full_name"] = row[0]
            d["email"] = row[1]
            d["student_id"] = row[2] 
            d["campus"] = row[3]
            d["timestamp_inserted"] = row[4]
            d["photo_filepath"] = row[5]
            d["license_filepath"] = row[6]
            d["request_id"] = row[7]
            pending_requests.append(d)

        
        cursor.execute("select count(*) from submissions where status='R'")
        total_rejected = cursor.fetchone()[0]
        rejected_pages = (total_rejected + per_page - 1) // per_page
        rejected_previous_page = page - 1 if page > 1 else None
        rejected_next_page = page + 1 if page < rejected_pages else None

        cursor.execute("""select first_name || ' ' || last_name as full_name, email, student_id, campus, 
                       to_char(timestamp_inserted, 'yyyy-mm-dd hh12:mi:ss AM') as timestamp_inserted,
                       photo_filepath, license_filepath, comments, request_id
                       from submissions where status='R' order by request_id limit %s offset %s""", (per_page, offset))
        rows = cursor.fetchall()

        for row in rows:
            d = {}
            d["full_name"] = row[0]
            d["email"] = row[1]
            d["student_id"] = row[2] 
            d["campus"] = row[3]
            d["timestamp_inserted"] = row[4]
            d["photo_filepath"] = row[5]
            d["license_filepath"] = row[6]
            d["comments"] = row[7]
            d["request_id"] = row[8]
            rejected_requests.append(d)
        
        cursor.execute("select count(*) from submissions where status='A'")
        total_approved = cursor.fetchone()[0]
        approved_pages = (total_approved + per_page - 1) // per_page
        approved_previous_page = page - 1 if page > 1 else None
        approved_next_page = page + 1 if page < approved_pages else None

        cursor.execute("""select first_name || ' ' || last_name as full_name, email, student_id, campus, 
                       to_char(timestamp_inserted, 'yyyy-mm-dd hh12:mi:ss AM') as timestamp_inserted,
                       photo_filepath, license_filepath, request_id
                       from submissions where status='A' order by request_id limit %s offset %s""", (per_page, offset))
        rows = cursor.fetchall()

        for row in rows:
            d = {}
            d["full_name"] = row[0]
            d["email"] = row[1]
            d["student_id"] = row[2] 
            d["campus"] = row[3]
            d["timestamp_inserted"] = row[4]
            d["photo_filepath"] = row[5]
            d["license_filepath"] = row[6]
            d["request_id"] = row[7]
            approved_requests.append(d)
        cursor.close()
        conn.close()  
    except:
        print(traceback.format_exc())
        if cursor:
            cursor.close()
        if conn:
            conn.close()
            return False
    return {
        "admins": admins,
        "pending_requests": pending_requests,
        "rejected_requests": rejected_requests,
        "approved_requests": approved_requests,
        "admin_pagination": {
            "prev_page": admin_prev_page,
            "next_page": admin_next_page,
            "total_pages": admin_pages,
        },
        "approved_pagination": {
            "total_pages": approved_pages,
            "next_page": approved_next_page,
            "prev_page": approved_previous_page,
        },
        "rejected_pagination": {
            "total_pages": rejected_pages,
            "next_page": rejected_next_page,
            "prev_page": rejected_previous_page,
        },
        "pending_pagination": {
            "total_pages": pending_pages,
            "next_page": pending_next_page,
            "prev_page": pending_previous_page,
        }
    }
def create_submission(photo_filepath, license_filepath):
    first_name = session["first_name"][0].decode()
    last_name = session["last_name"][0].decode()
    student_id = session["student_id"][0].decode()
    campus = session["campus"][0].decode()
    email = session["mail"][0].decode()

    params = get_db_params()

    try:
        conn = psycopg2.connect(**params)
        cursor = conn.cursor()
        cursor.execute("""insert into submissions 
                       (first_name, last_name, email, student_id, campus, photo_filepath, license_filepath)
                       values (%s, %s, %s, %s, %s, %s, %s)""",
                       (first_name, last_name, email, student_id, campus, photo_filepath, license_filepath))
        conn.commit()
        cursor.close()
        conn.close()
    except:
        print(traceback.format_exc())
        if cursor:
            cursor.close()
        if conn:
            conn.close()
        return False
    return True

def approve_request(request_id) -> bool:
    params = get_db_params()

    try:
        conn = psycopg2.connect(**params)
        cursor = conn.cursor()
        cursor.execute("update submissions set status=%s where request_id=%s", ('A', request_id))
        conn.commit()
        cursor.close()
        conn.close()
    except:
        print(traceback.format_exc())
        if cursor:
            cursor.close()
        if conn:
            conn.close()
        return False
    return True

def reject_request(request_id, comments) -> bool:
    params = get_db_params()

    try:
        conn = psycopg2.connect(**params)
        cursor = conn.cursor()
        cursor.execute("update submissions set status=%s, comments=%s where request_id=%s", ('R', comments, request_id))
        conn.commit()
        cursor.close()
        conn.close()
    except:
        print(traceback.format_exc())
        if cursor:
            cursor.close()
        if conn:
            conn.close()
        return False
    return True

def update_admin_password(username, new_password) -> bool:
    params = get_db_params()

    new_password = new_password.encode('utf-8')
    salt = bcrypt.gensalt()
    hashed_password = bcrypt.hashpw(new_password, salt).decode("utf-8")

    try:
        conn = psycopg2.connect(**params)
        cursor = conn.cursor()
        cursor.execute("select password from admins where username=%s", (username,))
        row = cursor.fetchone()
        if not row:
            return False
        if bcrypt.checkpw(new_password, row[0].encode("utf-8")):
            flash("New password cannot be the same as the old password", "danger")
            return False
        cursor.execute("update admins set password=%s, on_login=0 where username=%s", (hashed_password, username))
        conn.commit()
        cursor.close()
        conn.close()
    except:
        print(traceback.format_exc())
        if cursor:
            cursor.close()
        if conn:
            conn.close()
        return False
    return True

def compare_password(username, current_password) -> bool:
    params = get_db_params()
    try:
        conn = psycopg2.connect(**params)
        cursor = conn.cursor()
        cursor.execute("select password from admins where username=%s", (username,))
        row = cursor.fetchone()
        if not row:
            return False
        db_password = row[0]
        if not bcrypt.checkpw(current_password.encode("utf-8"), db_password.encode("utf-8")):
            return False
    except:
        print(traceback.format_exc())
        if cursor:
            cursor.close()
        if conn:
            conn.close()
        return False
    
    return True