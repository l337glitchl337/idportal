from flask import request
from factories import get_logger
import json
import ldap

class LDAPService:
    def __init__(self, auth_service=None, app=None):
        self.ldap_server = app.config["LDAP_URI"]
        self.ldap_bind_dn = app.config["LDAP_BIND_DN"]
        self.ldap_bind_pwd = app.config["LDAP_BIND_PWD"]
        self.ldap_search_base = app.config["LDAP_SEARCH_BASE"]
        self.ldap_search_filter = app.config["LDAP_SEARCH_FILTER"]
        self.ldap_attributes = json.loads(app.config["LDAP_ATTRIBUTES"])
        self.ldap_attributes_keys = list(self.ldap_attributes.values())
        self.auth_service = auth_service
        self.logger = get_logger("ldap_service")
        self.logger.info("LDAPService initialized.")

    def search_user(self, email) -> str:
        try:
            conn = ldap.initialize(self.ldap_server)
            conn.simple_bind_s(self.ldap_bind_dn, self.ldap_bind_pwd)
            filter = self.ldap_search_filter.replace("OBJ", email)
            results = conn.search_s(self.ldap_search_base, ldap.SCOPE_SUBTREE, filter, self.ldap_attributes_keys)
            conn.unbind_s()
        except Exception:
            self.logger.exception("An LDAP error as occured while searching for a user!")
            return None, False
        
        attrs = {}
        if results:
            dn, entry = results[0]
            for display_name, ldap_key in self.ldap_attributes.items():
                attrs[display_name] = entry.get(ldap_key, [None])[0].decode()
        return dn, attrs

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
                self.logger.info(f"Succesfully authenticated {email} - {dn}")
                return attrs, True
            except Exception:
                self.logger.exception(f"An error occured while trying to bind {email} - {dn}")
                self.auth_service.check_bfa(email, request.remote_addr, True)
                return None, False
        else:
            return None, False
        