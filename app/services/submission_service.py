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

        row = self.db.execute_query("""insert into submissions
                                       (first_name, last_name, email, id_number,
                                       location, photo_filepath, license_filepath)
                                       values (%s, %s, %s, %s, %s, %s, %s)
                                       RETURNING request_id""",
                                       (first_name, last_name, email, id_number,
                                        location, photo_filepath, license_filepath),
                                       fetch_one=True)
        if not row:
            return False
        session["request_id"] = row[0]
        self.logger.info(f"Succesfully created submission for {email}")
        return True
    
    def approve_request(self, request_id, actor=None) -> bool:
        result = self.db.execute_query("update submissions set status=%s where request_id=%s", ('A', request_id))
        if not result:
            return False
        self.logger.info(f"[AUDIT] request_id={request_id} approved by admin={actor}")
        self.mail.send_approved_email(request_id)
        return True

    def reject_request(self, request_id, comments, actor=None) -> bool:
        result = self.db.execute_query("update submissions set status=%s, comments=%s where request_id=%s", ('R', comments, request_id))
        if not result:
            return False
        self.logger.info(f"[AUDIT] request_id={request_id} rejected by admin={actor} comments=[{comments}]")
        self.mail.send_rejection_email(request_id, comments)
        return True

    def search(self, search_term, page=1, per_page=15) -> dict:
        offset = (page - 1) * per_page
        count_row = self.db.execute_query(
            "SELECT count(*) FROM submissions WHERE search_vector @@ plainto_tsquery(%s)",
            (search_term,), fetch_one=True)
        total = count_row[0] if count_row else 0
        if total == 0:
            return None
        rows = self.db.execute_query(
            "SELECT * FROM submissions WHERE search_vector @@ plainto_tsquery(%s) ORDER BY request_id LIMIT %s OFFSET %s",
            (search_term, per_page, offset), fetch_all=True, dict_cursor=True)
        total_pages = (total + per_page - 1) // per_page
        return {
            "search_results": [row for row in rows],
            "search_pagination": {
                "total_pages": total_pages,
                "next_page": page + 1 if page < total_pages else None,
                "prev_page": page - 1 if page > 1 else None
            }
        }

    def delete(self, request_id, actor=None) -> bool:
        r = self.db.execute_query("delete from submissions where request_id=%s", (request_id,))
        if not r:
            return False
        self.logger.info(f"[AUDIT] request_id={request_id} deleted by admin={actor}")
        return True
