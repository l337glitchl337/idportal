import bcrypt
from flask import session

class AdminService:
    def __init__(self, db=None):
        self.db = db
    
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
            return True
    
    def populate_admin_panel(self, page=1, per_page=15) -> dict:
        admins = []
        pending_requests = []
        approved_requests = []
        rejected_requests = []
        offset = (page - 1) * per_page

        row = self.db.execute_query("select count(*) from admins", fetch_one=True)
        total_admins = row[0]
        admin_pages = (total_admins + per_page - 1) // per_page
        admin_prev_page = page - 1 if page > 1 else None
        admin_next_page = page + 1 if page < admin_pages else None

        if session["role"] == "super":
            rows = self.db.execute_query("select first_name || ' ' || last_name as full_name, email, username, role, id from admins order by id limit %s offset %s", 
                                  (per_page, offset), 
                                  fetch_all=True)
            for row in rows:
                d = {} 
                d["full_name"] = row[0]
                d["email"] = row[1]
                d["username"] = row[2]
                d["role"] = row[3]
                d["user_id"] = row[4]
                admins.append(d)

        row = self.db.execute_query("select count(*) from submissions where status='N'", fetch_one=True)
        total_pending = row[0]
        pending_pages = (total_pending + per_page - 1) // per_page
        pending_previous_page = page - 1 if page > 1 else None
        pending_next_page = page + 1 if page < pending_pages else None
        
        rows = self.db.execute_query("""select first_name || ' ' || last_name as full_name, email, student_id, campus, 
                    to_char(timestamp_inserted, 'yyyy-mm-dd hh12:mi:ss AM') as timestamp_inserted,
                    photo_filepath, license_filepath, request_id
                    from submissions where status='N' order by request_id limit %s offset %s""", (per_page, offset), fetch_all=True)
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

        
        row = self.db.execute_query("select count(*) from submissions where status='R'", fetch_one=True)
        total_rejected = row[0]
        rejected_pages = (total_rejected + per_page - 1) // per_page
        rejected_previous_page = page - 1 if page > 1 else None
        rejected_next_page = page + 1 if page < rejected_pages else None

        rows = self.db.execute_query("""select first_name || ' ' || last_name as full_name, email, student_id, campus, 
                    to_char(timestamp_inserted, 'yyyy-mm-dd hh12:mi:ss AM') as timestamp_inserted,
                    photo_filepath, license_filepath, comments, request_id
                    from submissions where status='R' order by request_id limit %s offset %s""", (per_page, offset), fetch_all=True)
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
        
        row = self.db.execute_query("select count(*) from submissions where status='A'", fetch_one=True)
        total_approved = row[0]
        approved_pages = (total_approved + per_page - 1) // per_page
        approved_previous_page = page - 1 if page > 1 else None
        approved_next_page = page + 1 if page < approved_pages else None

        rows = self.db.execute_query("""select first_name || ' ' || last_name as full_name, email, student_id, campus, 
                    to_char(timestamp_inserted, 'yyyy-mm-dd hh12:mi:ss AM') as timestamp_inserted,
                    photo_filepath, license_filepath, request_id
                    from submissions where status='A' order by request_id limit %s offset %s""", (per_page, offset), fetch_all=True)
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
    

    def edit_admin(self, user_id, first_name, last_name, username, email, role) -> bool:
            result = self.db.execute_query("""update admins set first_name=%s, 
                                           last_name=%s, username=%s, email=%s, role=%s where id=%s""",
                                           (first_name, last_name, username, email, role, user_id))
            if not result:
                return False
            return True
    
    def delete_admin(self, user_id) -> bool:
        result = self.db.execute_query("delete from admins where id=%s", (user_id,))
        if not result:
            return False
        return True
