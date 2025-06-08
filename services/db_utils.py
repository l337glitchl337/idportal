import psycopg2
from factories import get_logger

class Database:
    def __init__(self, app=None):
        self.db_params = {
            "dbname" : app.config["PG_DBNAME"],
            "user" : app.config["PG_USER"],
            "password" : app.config["PG_PWD"],
            "host" : app.config["PG_HOST"],
            "port" : app.config["PG_PORT"]
        }
        self.logger = get_logger("db_utils")
        self.logger.info("Database initialized.")
    
    def execute_query(self, query, params=(), fetch_one=False, fetch_all=False):
        try:
            with psycopg2.connect(**self.db_params) as conn:
                with conn.cursor() as cursor:
                    cursor.execute(query, params)
                    if fetch_one:
                        return cursor.fetchone()
                    elif fetch_all:
                        return cursor.fetchall()
                    else:
                        conn.commit()
        except Exception as e:
            self.logger.exception("An SQL error has occurred!")
            return None
        
        return True