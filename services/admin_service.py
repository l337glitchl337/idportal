import bcrypt
from flask import session
from factories import get_logger

class AdminService:
    def __init__(self, db=None):
        self.db = db
        self.logger = get_logger("admin_service")
        self.logger.info("AdminService initialized.")
    
    def create_admin(self, first_name, last_name, username, password, email, role) -> bool:
        password = password.encode('utf-8')
        salt = bcrypt.gensalt()
        hashed_password = bcrypt.hashpw(password, salt).decode("utf-8")
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
                total_admins = row[0]
                admin_pages = (total_admins + per_page - 1) // per_page
                admin_prev_page = page - 1 if page > 1 else None
                admin_next_page = page + 1 if page < admin_pages else None
                
                if session["role"] == "super":
                    rows = self.db.execute_query("select first_name || ' ' || last_name as full_name, email, username, role, id from admins order by id limit %s offset %s", 
                                        (per_page, offset), 
                                        fetch_all=True, dict_cursor=True)
                    
                    admins = [row for row in rows]

                    return {
                        "admins" : admins,
                        "admin_pagination": {
                            "total_pages" : admin_pages,
                            "next_page" : admin_next_page,
                            "prev_page" : admin_prev_page
                        }
                    }
                        
            case "pending":
                row = self.db.execute_query("select count(*) from submissions where status='N'", fetch_one=True)
                total_pending = row[0]
                pending_pages = (total_pending + per_page - 1) // per_page
                pending_previous_page = page - 1 if page > 1 else None
                pending_next_page = page + 1 if page < pending_pages else None
                
                rows = self.db.execute_query("""select first_name || ' ' || last_name as full_name, email, id_number, location, 
                            to_char(timestamp_inserted, 'yyyy-mm-dd hh12:mi:ss AM') as timestamp_inserted,
                            photo_filepath, license_filepath, request_id
                            from submissions where status='N' order by request_id limit %s offset %s""", (per_page, offset), fetch_all=True, dict_cursor=True)
                
                pending_requests = [row for row in rows]

                return {
                    "pending_requests" : pending_requests,
                    "pending_pagination": {
                        "total_pages" : pending_pages,
                        "next_page" : pending_next_page,
                        "prev_page" : pending_previous_page
                    }
                }

            case "rejected":
                row = self.db.execute_query("select count(*) from submissions where status='R'", fetch_one=True)
                total_rejected = row[0]
                rejected_pages = (total_rejected + per_page - 1) // per_page
                rejected_previous_page = page - 1 if page > 1 else None
                rejected_next_page = page + 1 if page < rejected_pages else None

                rows = self.db.execute_query("""select first_name || ' ' || last_name as full_name, email, id_number, location, 
                            to_char(timestamp_inserted, 'yyyy-mm-dd hh12:mi:ss AM') as timestamp_inserted,
                            photo_filepath, license_filepath, comments, request_id
                            from submissions where status='R' order by request_id limit %s offset %s""", (per_page, offset), fetch_all=True, dict_cursor=True)
                
                rejected_requests = [row for row in rows]

                return {
                    "rejected_requests" : rejected_requests,
                    "rejected_pagination": {
                        "total_pages" : rejected_pages,
                        "next_page" : rejected_next_page,
                        "prev_page" : rejected_previous_page
                    }
                }
        
            case "approved":
                row = self.db.execute_query("select count(*) from submissions where status='A'", fetch_one=True)
                total_approved = row[0]
                approved_pages = (total_approved + per_page - 1) // per_page
                approved_previous_page = page - 1 if page > 1 else None
                approved_next_page = page + 1 if page < approved_pages else None

                rows = self.db.execute_query("""select first_name || ' ' || last_name as full_name, email, id_number, location, 
                            to_char(timestamp_inserted, 'yyyy-mm-dd hh12:mi:ss AM') as timestamp_inserted,
                            photo_filepath, license_filepath, request_id
                            from submissions where status='A' order by request_id limit %s offset %s""", (per_page, offset), fetch_all=True, dict_cursor=True)
                
                approved_requests = [row for row in rows]

                return {
                    "approved_requests" : approved_requests,
                    "approved_pagination": {
                        "total_pages" : approved_pages,
                        "next_page" : approved_next_page,
                        "prev_page" : approved_previous_page
                    }
                }
            case _:
                return {"none":None}
    

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
