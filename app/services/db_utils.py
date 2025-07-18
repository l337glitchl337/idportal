import psycopg2
from factories import get_logger
from psycopg2.extras import RealDictCursor

class Database:
    def __init__(self, app=None):
        self.db_params = {
            "dbname" : app.config["POSTGRES_DB"],
            "user" : app.config["POSTGRES_USER"],
            "password" : app.config["POSTGRES_PASSWORD"],
            "host" : app.config["POSTGRES_HOST"],
            "port" : app.config["POSTGRES_PORT"]
        }
        self.logger = get_logger("db_utils")
        self.logger.info("Database initialized.")
    
    def execute_query(self, query, params=(), fetch_one=False, fetch_all=False, dict_cursor=False):
        try:
            with psycopg2.connect(**self.db_params) as conn:
                if not dict_cursor:
                    with conn.cursor() as cursor:
                        cursor.execute(query, params)
                        if fetch_one:
                            return cursor.fetchone()
                        elif fetch_all:
                            return cursor.fetchall()
                        else:
                            conn.commit()
                else:
                    with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                        cursor.execute(query, params)
                        if fetch_one:
                            return cursor.fetchone()
                        elif fetch_all:
                            return cursor.fetchall()
                        else:
                            conn.commit()
        except Exception:
            self.logger.exception("An SQL error has occurred!")
            return None
        
        return True