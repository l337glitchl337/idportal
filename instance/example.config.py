# This is an example config file for IDPortal.
# It is recommended to copy this file to instance/config.py and edit the values there.

# BASE FLASK CONFIG

# To generate a secret key run: 
# python -c "import secrets; print(secrets.token_urlsafe(64))" in your terminal
# Note: a secret key is required to run the app

SECRET_KEY              = "your-secret"

# LDAP CONFIGURATION
# The search filter key should point to whatever attribute you store the user's email in.
# OBJ will be substituted with the user's email address upon login for example:
# (mail=OBJ) or (userMail=OBJ), etc.

LDAP_URI                = "ldap://your-ldap-server:389" 
LDAP_BIND_DN            = "cn=admin,dc=example,dc=com" 
LDAP_BIND_PWD           = "your-ldap-password" 
LDAP_SEARCH_BASE        = "ou=Users,dc=example,dc=com" 
LDAP_SEARCH_FILTER      = "(mail=OBJ)"

# Branding, title for the website and logo

SITE_TITLE              = "Demo IDPortal" 
LOGO                    = "portal_logo.png" 
FORGOT_PASSWORD_URL     = "http://localhost:5000/forgot_password" 
REVIEW_REQUEST_URL      = "http://localhost:5000/admin_panel" 
COMPANY_NAME            = "Demo Company" 
COMPANY_ADDRESS         = "123 Wallaby Way" 
COMPANY_STATE_ZIP       = "New York, NY 10001" 
COMPANY_PHONE           = "(123) 456-7890" 
COMPANY_CURRENT_YEAR    = "2025" 
COMPANY_EMAIL_SIGNATURE = "Demo Company ID Portal Team" 


# Email config
# If you are wanting to use a local relay smtp server without authentication comment out
# the MAIL_USERNAME and MAIL_PASSWORD lines below

MAIL_SERVER             = "mx.example.com" 
MAIL_PORT               = "25" 
MAIL_USE_TLS            = "False" 
MAIL_USERNAME           = "admin@example.com" 
MAIL_PASSWORD           = "your-email-password" 
MAIL_DEFAULT_SENDER     = ("IDPortal Admin" , "no-reply-idportal@example.com")
MAIL_DEFAULT_RECIP      = "idportal-admins@example.com" 

# Postgres config

PG_DBNAME               = "idportal" 
PG_USER                 = "your_db_user" 
PG_PWD                  = "your_db_password" 
PG_HOST                 = "127.0.0.1" 
PG_PORT                 = "5432" 