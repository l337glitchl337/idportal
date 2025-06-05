from flask import request
import ldap
import traceback

class LDAPService:
    def __init__(self, auth_service=None, app=None):
        self.ldap_server = app.config["LDAP_URI"]
        self.ldap_bind_dn = app.config["LDAP_BIND_DN"]
        self.ldap_bind_pwd = app.config["LDAP_BIND_PWD"]
        self.ldap_search_base = app.config["LDAP_SEARCH_BASE"]
        self.ldap_search_filter = app.config["LDAP_SEARCH_FILTER"]
        self.auth_service = auth_service

    def search_user(self, email) -> str:
        try:
            conn = ldap.initialize(self.ldap_server)
            conn.simple_bind_s(self.ldap_bind_dn, self.ldap_bind_pwd)
        except:
            print("******************")
            print(f"Error: LDAP Error")
            print("******************")
            print(traceback.format_exc())
            return None, False
        
        filter = self.ldap_search_filter.replace("OBJ", email)
        results = conn.search_s(self.ldap_search_base, ldap.SCOPE_SUBTREE, filter)

        conn.unbind_s()

        if results:
            dn, attrs = results[0]
            return dn, attrs
        else:
            return None, False

    def auth_user(self, email, password) -> bool:
        if self.auth_service.check_bfa(email, request.remote_addr, False):
            dn, attrs = self.search_user(email)

            if not dn:
                return None, False
            
            try:
                conn = ldap.initialize(self.ldap_server)
                conn.simple_bind_s(dn, password)
                conn.unbind_s()
                attrs["dn"] = dn
                return attrs, True
            except:
                print("******************")
                print(f"Error: LDAP Error")
                print(f"DN = {dn}")
                print("******************")
                print(traceback.format_exc())
                self.auth_service.check_bfa(email, request.remote_addr, True)
                return None, False
        else:
            return None, False
        