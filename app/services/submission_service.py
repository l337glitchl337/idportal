from flask import session, flash
from factories import get_logger

class SubmissionService:
    def __init__(self, db=None, mail=None):
        self.db = db
        self.logger = get_logger("submission_service")
        self.logger.info("SubmissionService initialized")
        self.mail = mail

    def create_submission(self, photo_filepath, license_filepath):
        first_name = session["First Name"]
        last_name = session["Last Name"]
        id_number = session["ID Number"]
        location = session["Location"]
        email = session["Email"]

        result = self.db.execute_query("""insert into submissions 
                                       (first_name, last_name, email, id_number, 
                                       location, photo_filepath, license_filepath) 
                                       values (%s, %s, %s, %s, %s, %s, %s)""",
                                       (first_name, last_name, email, id_number, 
                                        location, photo_filepath, license_filepath))
        if not result:
            return False
        request_id = self.db.execute_query("select request_id from submissions where email=%s", (email,), fetch_one=True)
        session["request_id"] = request_id[0]
        self.logger.info(f"Succesfully created submission for {email}")
        return True
    
    def approve_request(self, request_id) -> bool:
        result = self.db.execute_query("update submissions set status=%s where request_id=%s", ('A', request_id))
        if not result:
            return False
        self.logger.info(f"Request id: {request_id} was approved.")
        self.mail.send_approved_email(request_id)
        return True
    
    def reject_request(self, request_id, comments) -> bool:
        result = self.db.execute_query("update submissions set status=%s, comments=%s where request_id=%s", ('R', comments, request_id))
        if not result:
            return False 
        self.logger.info(f"Request id: {request_id} was rejected.")
        self.logger.info(f"Rejection comments for request id {request_id}: [{comments}]")
        self.mail.send_rejection_email(request_id, comments)
        return True
    
    def search(self, search_term) -> dict:
        rows = self.db.execute_query("SELECT * FROM submissions WHERE search_vector @@ plainto_tsquery(%s);", (search_term,), fetch_all=True, dict_cursor=True)
        results = [row for row in rows]
        search_results = {"search_results":results}
        return search_results
    
    def delete(self, request_id) -> bool:
        r = self.db.execute_query("delete from submissions where request_id=%s", (request_id,),)
        if not r:
            return False
        return True
