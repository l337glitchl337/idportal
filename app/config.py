import os

class BaseConfig:
    #BASE FLASK CONFIG
    SECRET_KEY              = os.getenv("SECRET_KEY")
    UPLOAD_FOLDER           = os.getenv("UPLOAD_FOLDER")
    
    #LDAP CONFIGURATION
    LDAP_URI                = os.getenv("LDAP_URI")
    LDAP_BIND_DN            = os.getenv("LDAP_BIND_DN")
    LDAP_BIND_PWD           = os.getenv("LDAP_BIND_PWD")
    LDAP_SEARCH_BASE        = os.getenv("LDAP_SEARCH_BASE")
    LDAP_SEARCH_FILTER      = os.getenv("LDAP_SEARCH_FILTER")
    LDAP_ATTRIBUTES         = os.getenv("LDAP_ATTRIBUTES", "{}")
    LDAP_USE_TLS            = os.getenv("LDAP_USE_TLS")
    
    #Branding, title for the website and logo
    SITE_TITLE              = os.getenv("SITE_TITLE")
    LOGO                    = os.getenv("LOGO")
    USER_LOGIN_URL          = os.getenv("USER_LOGIN_URL")
    FORGOT_PASSWORD_URL     = os.getenv("FORGOT_PASSWORD_URL")
    REVIEW_REQUEST_URL      = os.getenv("REVIEW_REQUEST_URL")
    ADMIN_URL               = os.getenv("ADMIN_URL")
    COMPANY_NAME            = os.getenv("COMPANY_NAME")
    COMPANY_ADDRESS         = os.getenv("COMPANY_ADDRESS")
    COMPANY_STATE_ZIP       = os.getenv("COMPANY_STATE_ZIP")
    COMPANY_PHONE           = os.getenv("COMPANY_PHONE")
    COMPANY_CURRENT_YEAR    = os.getenv("COMPANY_CURRENT_YEAR")
    COMPANY_EMAIL_SIGNATURE = os.getenv("COMPANY_EMAIL_SIGNATURE")

    #Email config
    MAIL_SERVER             = os.getenv("MAIL_SERVER")
    MAIL_PORT               = os.getenv("MAIL_PORT")
    #MAIL_USE_TLS            = os.getenv("MAIL_USE_TLS")
    #MAIL_USERNAME           = os.getenv("MAIL_USERNAME")
    #MAIL_PASSWORD           = os.getenv("MAIL_PASSWORD")
    MAIL_DEFAULT_SENDER     = (os.getenv("MAIL_DEFAULT_SENDER"), os.getenv("MAIL_USERNAME"))
    MAIL_DEFAULT_RECIP      = os.getenv("MAIL_DEFAULT_RECIP")

    #Postgres config
    POSTGRES_DB                   = os.getenv("POSTGRES_DBNAME")
    POSTGRES_USER                 = os.getenv("POSTGRES_USER")
    POSTGRES_PASSWORD             = os.getenv("POSTGRES_PASSWORD")
    POSTGRES_HOST                 = os.getenv("POSTGRES_HOST")
    POSTGRES_PORT                 = os.getenv("POSTGRES_PORT")


class DevelopmentConfig(BaseConfig):
    DEBUG = True

class ProductionConfig(BaseConfig):
    DEBUG = False
