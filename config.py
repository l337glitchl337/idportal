import os

class BaseConfig:
    #BASE FLASK CONFIG
    SECRET_KEY           = os.getenv("SECRET_KEY")
    UPLOAD_FOLDER        = os.getenv("UPLOAD_FOLDER")
    MAX_CONTENT_LENGTH   = os.getenv("MAX_CONTENT_LENGTH")
    
    #LDAP CONFIGURATION
    LDAP_URI             = os.getenv("LDAP_URI")
    LDAP_BIND_DN         = os.getenv("LDAP_BIND_DN")
    LDAP_BIND_PWD        = os.getenv("LDAP_BIND_PWD")
    LDAP_SEARCH_BASE     = os.getenv("LDAP_SEARCH_BASE")
    LDAP_SEARCH_FILTER   = os.getenv("LDAP_SEARCH_FILTER")
    
    #Branding, title for the website and logo
    SITE_TITLE           = os.getenv("SITE_TITLE")
    LOGO                 = os.getenv("LOGO")
    FORGOT_PASSWORD_URL  = os.getenv("FORGOT_PASSWORD_URL")

    #Email config
    MAIL_SERVER          = os.getenv("MAIL_SERVER")
    MAIL_PORT            = os.getenv("MAIL_PORT")
    MAIL_USE_TLS         = os.getenv("MAIL_USE_TLS")
    MAIL_USERNAME        = os.getenv("MAIL_USERNAME")
    MAIL_PWD             = os.getenv("MAIL_PWD")
    MAIL_DEFAULT_SENDER  = os.getenv("MAIL_DEFAULT_SENDER")
    MAIL_DEFAULT_RECIP   = os.getenv("MAIL_DEFAULT_RECIP")

    #Postgres config
    PG_DBNAME            = os.getenv("PG_DBNAME")
    PG_USER              = os.getenv("PG_USER")
    PG_PWD               = os.getenv("PG_PWD")
    PG_HOST              = os.getenv("PG_HOST")
    PG_PORT              = os.getenv("PG_PORT")


class DevelopmentConfig(BaseConfig):
    DEBUG = True

class ProductionConfig(BaseConfig):
    DEBUG = False
