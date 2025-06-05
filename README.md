# ID Portal

ID Portal is a web-based tool designed for organizations to accept and manage ID submission requests efficiently and securely.

## Features

- Accepts ID submissions from users
- Admin dashboard for managing and reviewing submissions
- User authentication and lookup via LDAP
- Admin authentication and submission storage using PostgreSQL
## Deployment Notes

A Docker release is planned for easy deployment in the future.

### Prerequisites

- A running PostgreSQL instance
- An LDAP environment
- Python binaries for `psycopg2` and `ldap` modules

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
