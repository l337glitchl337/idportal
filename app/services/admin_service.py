import bcrypt
import secrets
from flask import session
from factories import get_logger
from helpers import UtilityHelper

class AdminService:
    def __init__(self, db=None):
        self.db = db
        self.logger = get_logger("admin_service")
        self.logger.info("AdminService initialized.")
    
    def create_admin(self, first_name, last_name, username, email, role) -> bool:
        random_password = secrets.token_urlsafe(32).encode('utf-8')
        salt = bcrypt.gensalt()
        hashed_password = bcrypt.hashpw(random_password, salt).decode("utf-8")
        result = self.db.execute_query(f"""
                              insert into admins
                            (first_name, last_name, username, password, email, role)
                            values (%s, %s, %s, %s, %s, %s)""", (first_name, last_name, username, 
                                                                hashed_password, email, role))
        if result:
            self.logger.info(f"Succesfully created admin account: {username}")
            return True
        self.logger.warning(f"Could not create admin account {username}!")
    
    def populate_admin_panel(self, page=1, per_page=15, active_tab=None) -> dict:
        offset = (page - 1) * per_page

        match active_tab:
            case "admins":
                row = self.db.execute_query("select count(*) from admins", fetch_one=True)
                if session["role"] == "super":
                    rows = self.db.execute_query(
                        "select first_name || ' ' || last_name as full_name, email, username, role, id from admins order by id limit %s offset %s",
                        (per_page, offset), fetch_all=True, dict_cursor=True)
                    return {
                        "admins": list(rows),
                        "admin_pagination": UtilityHelper.paginate(row[0], page, per_page),
                    }
                return {}

            case "pending":
                row = self.db.execute_query("select count(*) from submissions where status='N'", fetch_one=True)
                rows = self.db.execute_query(
                    """select first_name || ' ' || last_name as full_name, email, id_number, location,
                        to_char(timestamp_inserted, 'yyyy-mm-dd hh12:mi:ss AM') as timestamp_inserted,
                        photo_filepath, license_filepath, request_id
                        from submissions where status='N' order by request_id limit %s offset %s""",
                    (per_page, offset), fetch_all=True, dict_cursor=True)
                return {
                    "pending_requests": list(rows),
                    "pending_pagination": UtilityHelper.paginate(row[0], page, per_page),
                }

            case "rejected":
                row = self.db.execute_query("select count(*) from submissions where status='R'", fetch_one=True)
                rows = self.db.execute_query(
                    """select first_name || ' ' || last_name as full_name, email, id_number, location,
                        to_char(timestamp_inserted, 'yyyy-mm-dd hh12:mi:ss AM') as timestamp_inserted,
                        photo_filepath, license_filepath, comments, request_id
                        from submissions where status='R' order by request_id limit %s offset %s""",
                    (per_page, offset), fetch_all=True, dict_cursor=True)
                return {
                    "rejected_requests": list(rows),
                    "rejected_pagination": UtilityHelper.paginate(row[0], page, per_page),
                }

            case "approved":
                row = self.db.execute_query("select count(*) from submissions where status='A'", fetch_one=True)
                rows = self.db.execute_query(
                    """select first_name || ' ' || last_name as full_name, email, id_number, location,
                        to_char(timestamp_inserted, 'yyyy-mm-dd hh12:mi:ss AM') as timestamp_inserted,
                        photo_filepath, license_filepath, request_id
                        from submissions where status='A' order by request_id limit %s offset %s""",
                    (per_page, offset), fetch_all=True, dict_cursor=True)
                return {
                    "approved_requests": list(rows),
                    "approved_pagination": UtilityHelper.paginate(row[0], page, per_page),
                }

            case _:
                return {"none": None}
    

    def edit_admin(self, user_id, first_name, last_name, username, email, role) -> bool:
            result = self.db.execute_query("""update admins set first_name=%s, 
                                           last_name=%s, username=%s, email=%s, role=%s where id=%s""",
                                           (first_name, last_name, username, email, role, user_id))
            if not result:
                self.logger.warning(f"Could not edit admin account {username}")
                return False
            self.logger.info(f"Succesfully edited admin account {username}")
            return True
    
    def delete_admin(self, user_id) -> bool:
        result = self.db.execute_query("delete from admins where id=%s", (user_id,))
        if not result:
            self.logger.warning(f"Could not delete admin account {user_id}")
            return False
        self.logger.info(f"Succesfully deleted admin account {user_id}")
        return True
