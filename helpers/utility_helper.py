import os
import re
from werkzeug.utils import secure_filename
from uuid import uuid4
from flask import flash

class UtilityHelper:
    @staticmethod
    def generate_unique_filename(filename : str) -> str:
        filename = secure_filename(filename)
        _, extension = os.path.splitext(filename)
        return f"{uuid4()}{extension}"
    
    @staticmethod
    def check_password_complexity(password) -> bool:
        # Minimum 8 characters, at least one uppercase letter, one lowercase letter, one digit, and one special character
        pattern = pattern = r'^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[\W_]).{8,}$'
        result = bool(re.match(pattern, password))
        if not result:
            flash("Password must be a minimum 8 characters, at least one uppercase letter, one lowercase letter, one digit, and one special character", "danger")
            return result
        return result