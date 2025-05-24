For the ldap-python dependencies see: https://www.python-ldap.org/en/python-ldap-3.4.3/installing.html#build-prerequisites


python-ldap

Build prerequisites
The following software packages are required to be installed on the local system when building python-ldap:

Python including its development files
C compiler corresponding to your Python version (on Linux, it is usually gcc)
OpenLDAP client libs version 2.4.11 or later; it is not possible and not supported to build with prior versions.
OpenSSL (optional)
Cyrus SASL (optional)
Kerberos libraries, MIT or Heimdal (optional)

Alpine
Packages for building:

apk add build-base openldap-dev python3-dev

CentOS
Packages for building:
yum groupinstall "Development tools"
yum install openldap-devel python-devel

Debian
Packages for building and testing:

apt-get install build-essential python3-dev \
    libldap2-dev libsasl2-dev slapd ldap-utils tox \
    lcov valgrind

Note:
On older releases tox was called python-tox.

Fedora
Packages for building and testing:s
dnf group install development-tools

dnf install openldap-devel \
    python3-devel python3-tox \
    lcov clang-analyzer valgrind

Note:
openldap-2.4.45-2 (Fedora 26), openldap-2.4.45-4 (Fedora 27) or newer are required.