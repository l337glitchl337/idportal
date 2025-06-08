import bcrypt
from flask import session, flash, current_app, request
from uuid import uuid4
from factories import get_logger

class AuthService:
    def __init__(self, db=None):
        self.db = db
        self.logger = get_logger("auth_service")
        self.logger.info("AuthService initialized")
    
    def admin_login(self, username, password) -> bool:
        self.logger.info(f"[{request.remote_addr}] attempting to login with username: {username}")
        row = self.db.execute_query("""SELECT first_name, last_name, username, email,
                                    password, status, role, on_login,
                                    id FROM admins WHERE username = %s""", 
                                    (username,), fetch_one=True)
        if not row:
            self.logger.warning(f"[{request.remote_addr}] login failed for user: {username} - User not found")
            return False
        self.logger.debug(f"Row from db on admin loging: {row}")
        
        db_password = row[4]
        if not bcrypt.checkpw(password.encode("utf-8"), db_password.encode("utf-8")):
            self.logger.warning(f"[{request.remote_addr}] login failed for user: {username} - Incorrect password")
            return False
        session.clear()
        session["first_name"] = row[0]
        session["last_name"] = row[1]
        session["admin_username"] = row[2]
        session["email"] = row[3]
        session["role"] = row[6]
        session["on_login"] = row[7]
        session["user_id"] = row[8]
        self.logger.info(f"[{request.remote_addr}] login successful for user: {username}")
        return True
    
    def update_admin_password(self, email, new_password) -> bool:
        self.logger.info(f"{email} attempting to change password.")
        new_password = new_password.encode('utf-8')
        salt = bcrypt.gensalt()
        hashed_password = bcrypt.hashpw(new_password, salt).decode("utf-8")
        row = self.db.execute_query("select password from admins where email=%s", (email,), fetch_one=True)
        if not row:
            self.logger.error(f"{email} not found in admins table.")
            return False
        if bcrypt.checkpw(new_password, row[0].encode("utf-8")):
            self.logger.info(f"{email} attempted to change password that is already set.")
            flash("New password cannot be the same as the old password", "danger")
            return False
        result = self.db.execute_query("update admins set password=%s, on_login=0 where email=%s", (hashed_password, email))
        if not result:
            flash("Failed to update password", "danger")
            self.logger.info(f"{email} failed to change password.")
            return False
        self.logger.info(f"{email} succesfully changed password")
        flash("Password updated successfully", "success")
        return True
    
    def compare_password(self, email, current_password) -> bool:
        row = self.db.execute_query("select password from admins where email=%s", (email,), fetch_one=True)
        if not row:
            self.logger.warning(f"{email} not found in admins, unable to compare passwords.")
            return False
        db_password = row[0]
        if not bcrypt.checkpw(current_password.encode("utf-8"), db_password.encode("utf-8")):
            self.logger.warning(f"{email} - password doesn't match db password.")
            return False
        self.logger.info(f"{email} succesfully compared password.")
        return True

    def gen_random_forgot_password_link(self) -> str:
        token = uuid4().hex
        url = f"{current_app.config['FORGOT_PASSWORD_URL']}?token={token}"
        self.logger.debug(f"Token and url generated for forgot password request: {url}, {token}")
        return url, token
    
    def validate_forgot_password_token(self, token) -> bool:
        row = self.db.execute_query("""select a.email from admin_forgot_password b join 
                                    admins a on b.user_id=a.id where token=%s 
                                    and expire_after > now()""", (token,), fetch_one=True)
        if not row:
            self.logger.info(f"Unable to validate token {token}")
            return False
        self.logger.info(f"Token succesfully validated for user {row[0]}")
        self.logger.debug(f"Token: {token} email {row[0]}")
        return row[0]
    
    def del_forgot_password_token(self, token) -> bool:
        self.db.execute_query("delete from admin_forgot_password where token=%s", (token,))
        return True
    
    def set_session_attrs(self, attrs) -> bool:
        try:
            session.clear()
            session["email"] = attrs["dn"]
            session["first_name"] = attrs["givenName"]
            session["last_name"] = attrs["sn"]
            session["student_id"] = attrs["title"]
            session["campus"] = attrs["o"]
            session["cn"] = attrs["cn"]
            session["mail"] = attrs["mail"]
            self.logger.info(f"Succesfully set session attibutes for {attrs["mail"][0].decode()}")
            return True
        except:
            self.logger.error(f"Could not set session attributes for {attrs["email"][0].decode()}")
            return False
        
    def check_bfa(self, email, ip_address, failed) -> bool:
        row = self.db.execute_query("select * from bfa where email=%s", (email,), fetch_one=True)
        if row:
            if int(row[3]) < 3 and failed:
                self.db.execute_query("""
                            update bfa set failed_attempts=failed_attempts+1,
                            timestamp_inserted=now()
                            where email=%s""",
                            (email,)
                            )
            elif int(row[3]) >= 3 and not failed:
                row = self.db.execute_query("""select (now() - timestamp_inserted) >
                                interval '30 minutes' as is_older
                                from bfa
                                where email=%s""", (email,), fetch_one=True)
                if not bool(row[0]):
                    row = self.db.execute_query("""select timestamp_inserted + interval '30 minutes' from bfa where email=%s""", 
                                                (email,), fetch_one=True)
                    self.logger.warning(f"IP {ip_address} has failed to login into '{email}' 3 times!")
                    self.logger.warning(f"{email} is now locked until {row[0]}")
                    return False
                else:
                    self.db.execute_query("delete from bfa where email=%s", (email,))
                    return True
        elif not row and failed:
            row = self.db.execute_query(f"""
                        insert into bfa (email, ip_address)
                        values ('{email}', '{ip_address}'::inet)""",
                        (email, ip_address))
        return True