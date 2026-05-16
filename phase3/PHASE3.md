# Phase 3: AWS Deployment (EC2 + Docker Compose + RDS)

## Context
Moving the phase2 Docker Compose app to AWS. Goal: nginx publicly accessible via an Elastic IP so the local `client.py` can reach it over the internet. Single-instance proof of concept — no orchestration, no load balancer, no scaling. Uses EC2 + Docker Compose (reusing the phase2 setup) with RDS for the database.

Tooling: AWS Console + CLI.

## Architecture

```
[Internet]
    |
[Elastic IP] → [EC2 t2.micro : port 80]
  [Docker Compose]
    ├── nginx container  (host 80 → container 80)
    └── server container (port 8000, internal only)
         |
[RDS db.t3.micro - PostgreSQL] (default VPC, not publicly accessible)
```

The local `client.py` connects to `http://<elastic-ip>/message`.

## Files in phase3/

### Already copied (no edits needed)
| File | Source | Notes |
|------|--------|-------|
| `Dockerfile.server` | `phase2/Dockerfile.server` | No changes needed |
| `server.py` | `phase2/server.py` | No changes needed |
| `requirements.txt` | `phase2/requirements.txt` | No changes needed |
| `nginx.conf` | `phase2/nginx.conf` | `proxy_pass http://server:8000` works via Docker Compose networking |
| `init.sql` | `phase2/init.sql` | Run against RDS to initialize schema |
| `client.py` | root `client.py` | Update `SERVER_URL` to Elastic IP before use |

### Created this session
| File | Notes |
|------|-------|
| `Dockerfile.nginx` | Bakes `nginx.conf` into `nginx:alpine` image |
| `docker-compose.yml` | nginx + server only (no db service — RDS handles it); uses `env_file: .env` |
| `.env.template` | Template for env vars; copy to `.env` on EC2 and fill in RDS values |

---

## Current Status
**All local files are complete.** Next step: begin AWS setup at Step 1 (Security Groups).

---

## Step-by-Step Deployment

### 1. Security Groups
Create two security groups in the default VPC (Console: EC2 → Security Groups → Create):

**ec2-sg**
| Rule | Port | Source |
|------|------|--------|
| Inbound | 80 | `0.0.0.0/0` (nginx, public) |
| Inbound | 22 | Your IP (SSH) |
| Outbound | all | `0.0.0.0/0` |

**rds-sg**
| Rule | Port | Source |
|------|------|--------|
| Inbound | 5432 | `ec2-sg` |
| Outbound | all | `0.0.0.0/0` |

### 2. RDS — PostgreSQL
Console: RDS → Create database
- Engine: PostgreSQL, free tier template
- Instance: `db.t3.micro`, 20 GiB gp2, single-AZ
- DB name: `devproject`, master username: `ty`, set a password
- VPC: default VPC; assign `rds-sg`
- **Disable** public accessibility
- After creation, note the endpoint hostname → used as `DB_HOST` in `.env`

### 3. EC2 Instance
Console: EC2 → Launch Instance
- AMI: Amazon Linux 2023
- Instance type: `t2.micro`
- Subnet: any default VPC public subnet
- Security group: `ec2-sg`
- Key pair: create or select one for SSH access

SSH in and install Docker:
```bash
ssh -i <key.pem> ec2-user@<ec2-public-ip>
sudo dnf update -y
sudo dnf install -y docker
sudo systemctl enable --now docker
sudo usermod -aG docker ec2-user
# Log out and back in so the docker group takes effect
exit
ssh -i <key.pem> ec2-user@<ec2-public-ip>
```

Install Docker Compose plugin:
```bash
sudo mkdir -p /usr/local/lib/docker/cli-plugins
sudo curl -SL https://github.com/docker/compose/releases/latest/download/docker-compose-linux-x86_64 \
  -o /usr/local/lib/docker/cli-plugins/docker-compose
sudo chmod +x /usr/local/lib/docker/cli-plugins/docker-compose
docker compose version   # verify
```

### 4. Elastic IP
Console: EC2 → Elastic IPs → Allocate Elastic IP address → Associate with your EC2 instance.

This is the permanent IP your `client.py` will point at.

### 5. Copy Files to EC2
From your local machine:
```bash
scp -i <key.pem> -r /home/ty/Desktop/code/dev-project/phase3/ ec2-user@<elastic-ip>:~/phase3/
```

### 6. Configure Environment on EC2
```bash
cd ~/phase3
cp .env.template .env
nano .env   # fill in DB_PASSWORD and DB_HOST (the RDS endpoint)
```

### 7. Initialize RDS Schema
Install the PostgreSQL client on EC2, then run `init.sql`:
```bash
sudo dnf install -y postgresql15
psql -h <rds-endpoint> -U ty -d devproject -f ~/phase3/init.sql
```

### 8. Start the App
```bash
cd ~/phase3
docker compose up --build -d
docker compose ps       # both containers should be Up
docker compose logs -f  # tail logs to verify no errors
```

### 9. Test End-to-End
Update `SERVER_URL` in your local `phase3/client.py`:
```python
SERVER_URL = "http://<elastic-ip>/message"
```
Run the client locally:
```bash
python3 phase3/client.py
```
Verify rows appear in RDS:
```bash
psql -h <rds-endpoint> -U ty -d devproject -c 'SELECT * FROM messages;'
```

---

## Tear Down
```bash
# On EC2
cd ~/phase3 && docker compose down

# AWS Console (to avoid ongoing charges)
# 1. Disassociate and release the Elastic IP
# 2. Terminate the EC2 instance
# 3. Delete the RDS instance (skip final snapshot for a PoC)
# 4. Delete ec2-sg and rds-sg
```

---

## Files Summary
| File | Status | Role |
|------|--------|------|
| `phase3/Dockerfile.server` | copied | Server image |
| `phase3/server.py` | copied | Flask app |
| `phase3/requirements.txt` | copied | Python deps |
| `phase3/nginx.conf` | copied | nginx config |
| `phase3/init.sql` | copied | Initialize RDS schema |
| `phase3/client.py` | copied | Update `SERVER_URL` to Elastic IP |
| `phase3/Dockerfile.nginx` | done | Bakes nginx.conf into image |
| `phase3/docker-compose.yml` | done | nginx + server (no db service) |
| `phase3/.env.template` | done | Env var template; fill in on EC2 |
