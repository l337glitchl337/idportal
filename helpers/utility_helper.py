import os
from werkzeug.utils import secure_filename
from uuid import uuid4

class UtilityHelper:
    @staticmethod
    def generate_unique_filename(filename : str) -> str:
        filename = secure_filename(filename)
        _, extension = os.path.splitext(filename)
        return f"{uuid4()}{extension}"