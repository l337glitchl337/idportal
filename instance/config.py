# To generate a secret key run: 
# python -c "import secrets; print(secrets.token_urlsafe(64))" 
# in your terminal
# Note: a secret key is required to run the app

#SECRET_KEY           = "secret_key"
#UPLOAD_FOLDER         = "uploads"
MAX_CONTENT_LENGTH    = 10 * 1024 * 1024

#LDAP CONFIGURATION

#LDAP_URI             = "ldap://localhost:389"
#LDAP_BIND_DN         = "cn=admin1,dc=example,dc=com"
#LDAP_BIND_PWD        = "ldap_password"
#LDAP_SEARCH_BASE     = "ou=Students,dc=example,dc=com"

# The LDAP_SEARCH_FILTER key should point to whatever attribute you store the users email in
# OBJ will be substituted with the users email address upon login
# If your attribute name differs make sure the synax is the same IE:
# (email=OBJ) or (userMail=OBJ), etc

LDAP_SEARCH_FILTER    = "(mail=OBJ)"

# Branding (logo and title of site)
# All logos need to be put in the static/ directory in the root of the web app

#SITE_TITLE           = "My Org ID Request"
#LOGO                 = "my_logo.png"
#FAVICON              = "my_favicon.svg"