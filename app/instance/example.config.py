# This is an example config file for IDPortal.
# It is recommended to copy this file to instance/config.py and edit the values there.

# LDAP CONFIGURATION
# The search filter key should point to whatever attribute you store the user's email in.
# OBJ will be substituted with the user's email address upon login for example:
# (mail=OBJ) or (userMail=OBJ), etc.

LDAP_URI                = "ldap://your-ldap-server:389" 
LDAP_BIND_DN            = "cn=admin,dc=example,dc=com" 
LDAP_BIND_PWD           = "your-ldap-password" 
LDAP_SEARCH_BASE        = "ou=Users,dc=example,dc=com" 
LDAP_SEARCH_FILTER      = "(mail=OBJ)"
LDAP_USE_TLS            = True

# LDAP_ATTRIBUTES is a JSON-formatted string that maps user-friendly key names to their corresponding LDAP attributes.
# For example, in a development environment, 'givenName' might represent the user's first name, while 'title' might represent the user ID.
# These key names are used in session variables and other parts of IDPortal to perform various tasks. 
# Do not modify or remove the key names; only update the values to match your LDAP instance's attribute names.
LDAP_ATTRIBUTES         = '{"First Name":"givenName","Last Name":"sn","ID Number":"title","Location":"o","cn":"cn","Email":"mail"}'

# Branding, title for the website and logo


# If you want to use a different logo, place them in static/ and put the change the LOGO key to the filename of your logo.
SITE_TITLE              = "Demo IDPortal" 
LOGO                    = "portal_logo.png" 
# The FORGOT_PASSWORD_URL and REVIEW_REQUEST_URL will just be the links that will redirect you back to idportal from emails
# Only edit the http://localhost portion, leave forgot_password and admin_panel the same or it will not work.
FORGOT_PASSWORD_URL     = "http://localhost/forgot_password" 
REVIEW_REQUEST_URL      = "http://localhost/admin_panel" 
USER_LOGIN_URL          = "http://localhost"
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
MAIL_USE_TLS            = False
MAIL_USERNAME           = "admin@example.com" 
MAIL_PASSWORD           = "your-email-password" 
MAIL_DEFAULT_SENDER     = ("IDPortal Admin" , "no-reply-idportal@example.com")
MAIL_DEFAULT_RECIP      = "idportal-admins@example.com" 
