import os
import re
from werkzeug.utils import secure_filename
from uuid import uuid4
from flask import flash

ALLOWED_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.webp'}

class UtilityHelper:
    @staticmethod
    def generate_unique_filename(filename : str) -> str:
        filename = secure_filename(filename)
        _, extension = os.path.splitext(filename)
        return f"{uuid4()}{extension}"

    @staticmethod
    def is_valid_image(file_storage) -> bool:
        _, ext = os.path.splitext(secure_filename(file_storage.filename))
        if ext.lower() not in ALLOWED_EXTENSIONS:
            return False
        header = file_storage.stream.read(12)
        file_storage.stream.seek(0)
        if header[:3] == b'\xff\xd8\xff':
            return True
        if header[:8] == b'\x89PNG\r\n\x1a\n':
            return True
        if header[:4] == b'RIFF' and header[8:12] == b'WEBP':
            return True
        return False

    @staticmethod
    def check_password_complexity(password) -> bool:
        if len(password) > 128:
            flash("Password must be 128 characters or fewer.", "danger")
            return False
        pattern = r'^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[\W_]).{8,}$'
        result = bool(re.match(pattern, password))
        if not result:
            flash("Password must be at least 8 characters with uppercase, lowercase, digit, and special character.", "danger")
        return result