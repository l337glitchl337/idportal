#!/bin/bash

SECRET_KEY=$(python -c "import secrets; print(secrets.token_urlsafe(64))")
POSTGRES_PASSWORD=$(python -c "from uuid import uuid4; print(uuid4().hex)")

echo "SECRET_KEY=$SECRET_KEY" >> .env
echo "POSTGRES_PASSWORD=$POSTGRES_PASSWORD" >> .env
echo "POSTGRES_DB=idportal" >> .env
echo "POSTGRES_USER=idportal" >> .env
echo "POSTGRES_PORT=5432" >> .env
echo "POSTGRES_HOST=db" >> .env
echo "LOGO=portal_logo.png" >> .env

echo "Environment file created"
echo "------------------------"
cat .env


echo "Setting up nginx ssl config.."
mkdir docker/nginx/certs 2>/dev/null && echo "Created docker/nginx/certs" || echo "docker/nginx/certs already exists, continuing."

read -p "Would you like to create a self signed cert for testing?[y\n]:> " prompt
prompt=$(echo $prompt | tr '[:upper:]' '[:lower:]')

if [[ "$prompt" == "y" ]]
then
    openssl req -x509 -nodes -days 365 -newkey rsa:2048 -keyout docker/nginx/certs/key.pem -out docker/nginx/certs/cert.pem -subj "/C=US/ST=State/L=City/O=Org/OU=Dept/CN=localhost"
    echo "Creating nginx config for SSL..."
    mv docker/nginx/nginx.conf docker/nginx/nginx.no.ssl.conf
    mv docker/nginx/nginx.ssl.conf docker/nginx/nginx.conf
else
    echo "Leaving nginx as is."
fi
echo "Done"