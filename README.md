# ID Portal

ID Portal is a web-based tool designed for organizations to accept and manage ID submission requests efficiently and securely.

## Features

- Accepts ID submissions from users
- Admin dashboard for managing and reviewing submissions
- User authentication and lookup via LDAP
- Admin authentication and submission storage using PostgreSQL

## Deployment Notes

A Docker release is planned for easy deployment in the future.

## Prerequisites
Python 3.10 or greater
Postgres installation
LDAP Instance

Packages:

libpq-devel 
openldap-devel 
gcc 
python3.12-devel

## Basic installation

**Note this basic installiation is just for testing and is not production ready**

Download repo:
```gh repo clone l337glitchl337/idportal```

Create a venv (optional):

```
cd idportal-main
python -m venv venv
```

Activate venv:

```
. venv/bin/activate
```

Install depenencies:

```
sudo dnf install libpq-devel openldap-devel gcc python[VERSION]-devel
```

Now, install required modules:

```
pip install -r requirements.txt
```

Installing is now complete, now you will need to look at the instance/example.config.py file to set up your IDPortal instance

Run app:

```
flask run
```

Or run on all interfaces:

```
flask run --host=0.0.0.0
```


### Configuration

Application configuration files are located in the `instance/` directory. Refer to `example.config.py` for an example configuration setup.
## Tech Stack

- **Backend:** Python, Flask
- **Database:** PostgreSQL
- **Authentication:** LDAP (users), PostgreSQL (admins)
- **Frontend:** HTML, Bootstrap CSS, Vanilla JavaScript, Bootstrap JS

## Getting Started

1. **Clone the repository**
    ```bash
    git clone https://github.com/your-org/idportal.git
    cd idportal
    ```

2. **Install dependencies**
    ```bash
    pip install -r requirements.txt
    ```

3. **Configure environment variables**
    - Set up PostgreSQL connection details
    - Configure LDAP server settings

4. **Run the application**
    ```bash
    flask run
    ```

## License

This project is licensed under the MIT License.

## Contributing

Contributions are welcome! Please open issues or submit pull requests.
