from flask import request, flash
from factories import get_logger
from ldap.filter import escape_filter_chars
import json
import ldap

class LDAPService:
    def __init__(self, auth_service=None, app=None, db=None):
        self.ldap_server = app.config["LDAP_URI"]
        self.ldap_bind_dn = app.config["LDAP_BIND_DN"]
        self.ldap_bind_pwd = app.config["LDAP_BIND_PWD"]
        self.ldap_search_base = app.config["LDAP_SEARCH_BASE"]
        self.ldap_search_filter = app.config["LDAP_SEARCH_FILTER"]
        self.ldap_attributes = json.loads(app.config["LDAP_ATTRIBUTES"])
        self.ldap_attributes_keys = list(self.ldap_attributes.values())
        self.ldap_use_tls = app.config["LDAP_USE_TLS"]
        self.auth_service = auth_service
        self.db = db
        self.logger = get_logger("ldap_service")
        self.logger.info("LDAPService initialized.")

    def _start_tls(self, conn):
        ldap.set_option(ldap.OPT_X_TLS_REQUIRE_CERT, ldap.OPT_X_TLS_DEMAND)
        conn.start_tls_s()

    def search_user(self, email) -> tuple:
        conn = None
        try:
            conn = ldap.initialize(self.ldap_server)
            if self.ldap_use_tls.lower() == "true":
                self._start_tls(conn)
            conn.simple_bind_s(self.ldap_bind_dn, self.ldap_bind_pwd)
            filter_str = self.ldap_search_filter.replace("OBJ", escape_filter_chars(email))
            results = conn.search_s(self.ldap_search_base, ldap.SCOPE_SUBTREE, filter_str, self.ldap_attributes_keys)
        except Exception:
            self.logger.exception("An LDAP error occurred while searching for a user!")
            return None, {}
        finally:
            if conn:
                try:
                    conn.unbind_s()
                except Exception:
                    pass

        if not results:
            return None, {}
        dn, entry = results[0]
        attrs = {}
        for display_name, ldap_key in self.ldap_attributes.items():
            attrs[display_name] = entry.get(ldap_key, [None])[0].decode()
        return dn, attrs

    def auth_user(self, email, password) -> tuple:
        if self.auth_service.check_bfa(email, request.remote_addr, False):
            if not self.check_user_submissions(email):
                msg = "You have a submission that is already approved or pending, please contact your local administrator for more information."
                return msg, None, False
            dn, attrs = self.search_user(email)

            if not dn:
                return None, None, False

            conn = None
            try:
                conn = ldap.initialize(self.ldap_server)
                if self.ldap_use_tls.lower() == "true":
                    self._start_tls(conn)
                conn.simple_bind_s(dn, password)
                attrs["dn"] = dn
                self.logger.info(f"Succesfully authenticated {email} - {dn}")
                return None, attrs, True
            except Exception:
                self.logger.exception(f"An error occured while trying to bind {email} - {dn}")
                self.auth_service.check_bfa(email, request.remote_addr, True)
                return None, None, False
            finally:
                if conn:
                    try:
                        conn.unbind_s()
                    except Exception:
                        pass
        else:
            return None, None, False
        
    def check_user_submissions(self, email):
        count = self.db.execute_query("select count(*) from submissions where email=%s and status in ('N','A')", (email,), fetch_one=True)
        print(count[0])
        if count[0] >= 1:
            self.logger.warning(f"Not accepting submission from {email}")
            self.logger.warning(f"{email} has a pending or approved submission in the db.")
            return False
        return True
        