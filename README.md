# IDPortal

**IDPortal** is a web-based platform for submitting photo ID requests in organizational settings such as schools or workplaces. Users can log in with their organization's credentials (LDAP/Active Directory) and submit ID requests without needing to visit a physical office. IT administrators can review, approve, or deny requests via a secure admin panel, and use the submitted photos to print ID cards based on a template.

## 🛠 Tech Stack

- **Backend:** Python (Flask)
- **Frontend:** JavaScript, Bootstrap CSS
- **Database:** PostgreSQL
- **Authentication:** LDAP / Active Directory
- **Containerization:** Docker & Docker Compose
- **Web Server:** Nginx (with optional SSL)

## 📦 Installation Instructions

Follow these steps to install and run IDPortal:

### 1. Install Docker and Docker Compose

Install Docker and Docker Compose by following the official guide:  
https://docs.docker.com/engine/install/

### 2. Clone the Repository

```bash
git clone https://github.com/yourusername/idportal.git
cd idportal
```

### 3. Run Initialization Script

Run the included setup script to generate environment variables and configure SSL:

```bash
./init.sh
```

You will see output similar to:

```
Environment file created
------------------------
SECRET_KEY=randomkey
POSTGRES_PASSWORD=randompass
POSTGRES_DB=idportal
POSTGRES_USER=idportal
POSTGRES_PORT=5432
POSTGRES_HOST=db
LOGO=portal_logo.png

Setting up nginx ssl config..
docker/nginx/certs already exists, continuing.
Would you like to create a self signed cert for testing?[y\n]:> y
... [cert generation output] ...
Done
```

You can optionally create a self-signed certificate for testing by entering `y`.  
After testing, you can replace the generated cert and key in `docker/nginx/certs` with CA-signed versions for production.

**Note:** You may edit the `.env` file after it is generated to change passwords, usernames, or logo filename.

### 4. Build Docker Containers

Run the following command to build the Docker images and bring up the services:

```bash
docker compose up --build
```

Once the build is complete, press `Ctrl+C` to stop the containers.

### 5. Create Application Config File

Create the app config file at the following path inside the Docker volume:

```bash
sudo nano /var/lib/docker/volumes/idportal_config/_data/config.py
```

Refer to `example.config.py` in the project root to structure your configuration.  
This includes LDAP connection settings and application-specific options.

### 6. Start the Application

Now that the config file is in place, start the containers in detached mode:

```bash
docker compose up -d
```

### 7. Access the Portal

Open your browser and go to:

```
https://localhost
```

You can now log in with your organization's credentials and begin submitting or approving ID requests.

## 🔐 Additional Notes

- `.env` — Stores secrets and environment variables (e.g., DB credentials, Flask secret key)
- `docker/nginx/certs/` — Holds SSL certificates (self-signed or from a certificate authority)
- `/var/lib/docker/volumes/idportal_config/_data/config.py` — App-specific configuration file
- `/var/lib/docker/volumes/idportal_logs/_data` - Holds app-specific logs
- `/var/lib/docker/volumes/idportal_pgdata/_data` - Holds postgres database files
- `/var/lib/docker/volumes/idportal_uploads/_data` - Holds uploaded photos

## 📄 License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.

## 🤝 Contributing

Contributions, suggestions, and pull requests are welcome! Please submit issues or PRs to help improve IDPortal.