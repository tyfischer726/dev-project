#!/bin/bash

# Install Docker and git
dnf update -y
dnf install -y docker git
systemctl enable --now docker
usermod -aG docker ec2-user

# Docker Compose plugin
mkdir -p /usr/local/lib/docker/cli-plugins
curl -SL https://github.com/docker/compose/releases/latest/download/docker-compose-linux-x86_64 \
  -o /usr/local/lib/docker/cli-plugins/docker-compose
chmod +x /usr/local/lib/docker/cli-plugins/docker-compose

# Docker Buildx plugin
curl -SL $(curl -s https://api.github.com/repos/docker/buildx/releases/latest \
  | grep "browser_download_url.*linux-amd64\"" | cut -d'"' -f4) \
  -o /usr/local/lib/docker/cli-plugins/docker-buildx
chmod +x /usr/local/lib/docker/cli-plugins/docker-buildx

# Clone repo
git clone https://github.com/tyfischer726/dev-project.git /home/ec2-user/dev-project

# Write .env  (template vars are substituted by Terraform's templatefile() at apply time)
cat > /home/ec2-user/dev-project/phase3/.env <<EOF
DB_NAME=${db_name}
DB_USER=${db_username}
DB_PASSWORD=${db_password}
DB_HOST=${db_host}
EOF

# Wait for RDS to accept connections (takes several minutes after terraform apply)
dnf install -y postgresql15
until pg_isready -h ${db_host} -U ${db_username} -q; do
  echo "Waiting for RDS..."
  sleep 10
done

# Initialize schema
PGPASSWORD=${db_password} psql \
  -h ${db_host} \
  -U ${db_username} \
  -d ${db_name} \
  -f /home/ec2-user/dev-project/phase3/init.sql

# Start app (running as root; docker daemon is accessible)
cd /home/ec2-user/dev-project/phase3
docker compose up --build -d
