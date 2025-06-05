import traceback
from flask import session

class SubmissionService:
    def __init__(self, db=None):
        self.db = db

    def create_submission(self, photo_filepath, license_filepath):
        first_name = session["first_name"][0].decode()
        last_name = session["last_name"][0].decode()
        student_id = session["student_id"][0].decode()
        campus = session["campus"][0].decode()
        email = session["mail"][0].decode()
        result = self.db.execute_query("""insert into submissions 
                                       (first_name, last_name, email, student_id, 
                                       campus, photo_filepath, license_filepath) 
                                       values (%s, %s, %s, %s, %s, %s, %s)""",
                                       (first_name, last_name, email, student_id, 
                                        campus, photo_filepath, license_filepath))
        if not result:
            return False
        return True
    
    def approve_request(self, request_id) -> bool:
        result = self.db.execute_query("update submissions set status=%s where request_id=%s", ('A', request_id))
        if not result:
            return False
        return True
    
    def reject_request(self, request_id, comments) -> bool:
        result = self.db.execute_query("update submissions set status=%s, comments=%s where request_id=%s", ('R', comments, request_id))
        if not result:
            return False 
        return True