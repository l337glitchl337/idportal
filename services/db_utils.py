import psycopg2
import traceback

class Database:
    def __init__(self, app=None):
        self.db_params = {
            "dbname" : app.config["PG_DBNAME"],
            "user" : app.config["PG_USER"],
            "password" : app.config["PG_PWD"],
            "host" : app.config["PG_HOST"],
            "port" : app.config["PG_PORT"]
        }
    
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
            print(f"An error occurred: {e}")
            traceback.print_exc()
            return None
        return True