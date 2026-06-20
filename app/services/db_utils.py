from psycopg2.pool import ThreadedConnectionPool
from psycopg2.extras import RealDictCursor
from factories import get_logger

class Database:
    def __init__(self, app=None):
        self.pool = ThreadedConnectionPool(
            minconn=2,
            maxconn=10,
            dbname=app.config["POSTGRES_DB"],
            user=app.config["POSTGRES_USER"],
            password=app.config["POSTGRES_PASSWORD"],
            host=app.config["POSTGRES_HOST"],
            port=app.config["POSTGRES_PORT"]
        )
        self.logger = get_logger("db_utils")
        self.logger.info("Database pool initialized.")

    def execute_query(self, query, params=(), fetch_one=False, fetch_all=False, dict_cursor=False):
        conn = self.pool.getconn()
        try:
            cursor_factory = RealDictCursor if dict_cursor else None
            with conn.cursor(cursor_factory=cursor_factory) as cursor:
                cursor.execute(query, params)
                result = None
                if fetch_one:
                    result = cursor.fetchone()
                elif fetch_all:
                    result = cursor.fetchall()
                conn.commit()
                return result if (fetch_one or fetch_all) else True
        except Exception:
            conn.rollback()
            self.logger.exception("An SQL error has occurred!")
            return None
        finally:
            self.pool.putconn(conn)