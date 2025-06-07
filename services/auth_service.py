import bcrypt
from flask import session, flash, current_app
from uuid import uuid4
from factories import get_logger

class AuthService:
    def __init__(self, db=None):
        self.db = db
        self.logger = get_logger("auth_service")
    
    def admin_login(self, username, password) -> bool:
        self.logger.info(f"Attempting to login with username: {username}")
        row = self.db.execute_query("""SELECT first_name, last_name, username, username, 
                                    password, status, role, on_login, 
                                    id FROM admins WHERE username = %s""", 
                                    (username,), fetch_one=True)
        if not row:
            self.logger.warning(f"Login failed for username: {username} - User not found")
            return False
        
        db_password = row[4]
        if not bcrypt.checkpw(password.encode("utf-8"), db_password.encode("utf-8")):
            self.logger.warning(f"Login failed for username: {username} - Incorrect password")
            return False
        session["first_name"] = row[0]
        session["last_name"] = row[1]
        session["admin_username"] = row[2]
        session["username"] = row[3]
        session["role"] = row[6]
        session["on_login"] = row[7]
        session["user_id"] = row[8]
        self.logger.info(f"Login successful for username: {username}")
        return True
    
    def update_admin_password(self, username, new_password) -> bool:
        new_password = new_password.encode('utf-8')
        salt = bcrypt.gensalt()
        hashed_password = bcrypt.hashpw(new_password, salt).decode("utf-8")
        row = self.db.execute_query("select password from admins where username=%s", (username,), fetch_one=True)
        if not row:
            return False
        if bcrypt.checkpw(new_password, row[0].encode("utf-8")):
            flash("New password cannot be the same as the old password", "danger")
            return False
        result = self.db.execute_query("update admins set password=%s, on_login=0 where username=%s", (hashed_password, username))
        if not result:
            flash("Failed to update password", "danger")
            return False
        flash("Password updated successfully", "success")
        return True
    
    def compare_password(self, username, current_password) -> bool:
        row = self.db.execute_query("select password from admins where username=%s", (username,), fetch_one=True)
        if not row:
            return False
        db_password = row[0]
        if not bcrypt.checkpw(current_password.encode("utf-8"), db_password.encode("utf-8")):
            return False
        return True

    def gen_random_forgot_password_link(self) -> str:
        token = uuid4().hex
        return f"{current_app.config['FORGOT_PASSWORD_URL']}?token={token}", token
    
    def validate_forgot_password_token(self, token) -> bool:
        row = self.db.execute_query("""select a.username from admin_forgot_password b join 
                                    admins a on b.user_id=a.id where token=%s 
                                    and expire_after > now()""", (token,), fetch_one=True)
        if not row:
            return False
        return row[0]
    
    def del_forgot_password_token(self, token) -> bool:
        self.db.execute_query("delete from admin_forgot_password where token=%s", (token,))
        return True
    
    def set_session_attrs(self, attrs) -> bool:
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
        
    def check_bfa(self, username, ip_address, failed) -> bool:
        row = self.db.execute_query("select * from bfa where username=%s", (username,), fetch_one=True)
        if row:
            if int(row[3]) < 3 and failed:
                self.db.execute_query("""
                            update bfa set failed_attempts=failed_attempts+1,
                            timestamp_inserted=now()
                            where username=%s""",
                            (username,)
                            )
            elif int(row[3]) >= 3 and not failed:
                row = self.db.execute_query("""select (now() - timestamp_inserted) >
                                interval '30 minutes' as is_older
                                from bfa
                                where username=%s""", (username,), fetch_one=True)
                if not bool(row[0]):
                    row = self.db.execute_query("""select timestamp_inserted + interval '30 minutes' from bfa where username=%s""", 
                                                (username,), fetch_one=True)
                    print(f"""IP: {ip_address} has failed to login into '{username}' 3 times, \
account is locked out until {row[0]} authentication will not be tried until lockout has expired.""")
                    return False
                else:
                    self.db.execute_query("delete from bfa where username=%s", (username,))
                    return True
        elif not row and failed:
            row = self.db.execute_query(f"""
                        insert into bfa (username, ip_address)
                        values ('{username}', '{ip_address}'::inet)""",
                        (username, ip_address))
        if not row:
            return False
        return True