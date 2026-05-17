# Phase 3: AWS Deployment (EC2 + Docker Compose + RDS)

## Context
Moving the phase2 Docker Compose app to AWS. Goal: nginx publicly accessible via an Elastic IP so the local `client.py` can reach it over the internet. Single-instance proof of concept — no orchestration, no load balancer, no scaling. Uses EC2 + Docker Compose (reusing the phase2 setup) with RDS for the database.

Tooling: AWS Console for all resource creation. Terminal work (Docker install, git clone, docker compose) done via **EC2 Instance Connect** — the browser-based terminal in the AWS Console (EC2 → your instance → Connect → EC2 Instance Connect tab). No local AWS CLI or SSH needed.

## Architecture

```
dev-project-vpc (10.0.0.0/16)
├── public subnet 10.0.1.0/24 (AZ-a)
│     └── EC2 t2.micro ← public IP / Elastic IP (port 80)
│           [Docker Compose]
│             ├── nginx  (host 80 → container 80)
│             └── server (port 8000, internal only)
│                   |
├── private subnet A 10.0.2.0/24 (AZ-a)  ┐
└── private subnet B 10.0.3.0/24 (AZ-b)  ┘ DB subnet group
      └── RDS db.t3.micro (PostgreSQL, not publicly accessible)
```

The local `client.py` connects to `http://<public-ip>/message`.

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
**Complete and working.** EC2 + RDS deployed in `dev-project-vpc`. Client connects to EC2 public IP over the internet.

---

## Step-by-Step Deployment

### 1. VPC & Networking
Console: VPC → Your VPCs → Create VPC

**Create the VPC:**
- Name: `dev-project-vpc`
- IPv4 CIDR: `10.0.0.0/16`
- Leave everything else default → Create VPC

**Create three subnets** (VPC → Subnets → Create subnet, select `dev-project-vpc`):

| Name | CIDR | AZ | Purpose |
|------|------|----|---------|
| `public-a` | `10.0.1.0/24` | AZ-a (e.g. us-east-1a) | EC2 |
| `private-a` | `10.0.2.0/24` | AZ-a | RDS |
| `private-b` | `10.0.3.0/24` | AZ-b (e.g. us-east-1b) | RDS (AWS requires 2 AZs for RDS subnet group) |

**Enable auto-assign public IP on the public subnet:**
Select `public-a` → Actions → Edit subnet settings → Enable auto-assign public IPv4 → Save

**Create an Internet Gateway:**
- VPC → Internet Gateways → Create → Name: `dev-project-igw` → Create
- Actions → Attach to VPC → select `dev-project-vpc`

**Create a custom route table for the public subnet:**
- VPC → Route Tables → Create route table
- Name: `public-rt`, VPC: `dev-project-vpc` → Create
- Routes tab → Edit routes → Add route: `0.0.0.0/0` → Target: `dev-project-igw` → Save
- Subnet associations tab → Edit → associate `public-a` → Save

This overrides the main route table for `public-a` only. The private subnets stay implicitly on the main route table, which has only the local route — meaning no internet access for RDS.

**Important:** Do not add the IGW route to the main route table. The main route table should have only the `10.0.0.0/16 → local` rule that AWS created automatically. Adding the IGW route there would give all subnets internet routing, including the private ones.

**Create a DB Subnet Group** (done in RDS console, not VPC, but logically belongs here):
- RDS → Subnet groups → Create DB subnet group
- Name: `dev-project-db-subnet-group`
- VPC: `dev-project-vpc`
- Add subnets: select `private-a` and `private-b`
- Create

### 2. Security Groups
Console: EC2 → Security Groups → Create security group. **Set VPC to `dev-project-vpc`** for both.

**ec2-sg**
| Rule | Port | Source |
|------|------|--------|
| Inbound | 80 | `0.0.0.0/0` (nginx, public) |
| Inbound | 22 | Select "com.amazonaws.<region>.ec2-instance-connect |
| Outbound | all | `0.0.0.0/0` |

Note: browser-based EC2 Instance Connect routes through AWS's servers, not your local IP — so the SSH rule must allow AWS's IP range, not "My IP". The range above is specific to us-east-1.

**rds-sg**
| Rule | Port | Source |
|------|------|--------|
| Inbound | 5432 | `ec2-sg` |
| Outbound | all | `0.0.0.0/0` |

### 3. RDS — PostgreSQL
Console: RDS → Create database
- Engine: PostgreSQL, free tier template
- Instance: `db.t3.micro`, 20 GiB gp2, single-AZ
- DB name: `devproject`, master username: `ty`, set a password
- VPC: `dev-project-vpc`; subnet group: `dev-project-db-subnet-group`; security group: `rds-sg`
- **Disable** public accessibility
- After creation, note the endpoint hostname → used as `DB_HOST` in `.env`

### 4. EC2 Instance
Console: EC2 → Launch Instance
- AMI: Amazon Linux 2023
- Instance type: `t2.micro`
- VPC: `dev-project-vpc`; Subnet: `public-a`
- Security group: `ec2-sg`
- Key pair: proceed without a key pair (EC2 Instance Connect doesn't need one)

Open a terminal on the instance: Console → EC2 → select your instance → Connect → EC2 Instance Connect tab → Connect.

Install Docker:
```bash
sudo dnf update -y
sudo dnf install -y docker
sudo systemctl enable --now docker
sudo usermod -aG docker ec2-user
```

For the docker group to take effect, close the EC2 Instance Connect tab and reconnect (same Connect button).

Install Docker Compose plugin:
```bash
sudo mkdir -p /usr/local/lib/docker/cli-plugins
sudo curl -SL https://github.com/docker/compose/releases/latest/download/docker-compose-linux-x86_64 \
  -o /usr/local/lib/docker/cli-plugins/docker-compose
sudo chmod +x /usr/local/lib/docker/cli-plugins/docker-compose
docker compose version   # verify
```

Install Docker Buildx plugin (Amazon Linux 2023 ships with an older version that Docker Compose requires to be updated):
```bash
sudo curl -SL $(curl -s https://api.github.com/repos/docker/buildx/releases/latest \
  | grep "browser_download_url.*linux-amd64\"" | cut -d'"' -f4) \
  -o /usr/local/lib/docker/cli-plugins/docker-buildx
sudo chmod +x /usr/local/lib/docker/cli-plugins/docker-buildx
docker buildx version   # verify
```

### 5. Elastic IP (optional)
Console: EC2 → Elastic IPs → Allocate Elastic IP address → Associate with your EC2 instance.

This gives you a permanent IP that survives instance stop/start. Without it, the EC2 auto-assigned public IP changes every time the instance is stopped — meaning you'd have to update `SERVER_URL` in `client.py` each time. For a PoC where you leave the instance running, the auto-assigned IP is fine.

### 6. Clone the Repo on EC2
In the EC2 Instance Connect terminal:
```bash
git clone https://github.com/tyfischer726/dev-project.git
cd dev-project/phase3
```

### 7. Configure Environment on EC2
```bash
cp .env.template .env
nano .env   # fill in DB_PASSWORD and DB_HOST (the RDS endpoint)
```

Find the RDS endpoint: RDS → Databases → click your instance → **Connectivity & security** tab → Endpoint. It looks like `database-1.xxxxxxxxxxxx.us-east-1.rds.amazonaws.com`.

### 8. Initialize RDS Schema
Install the PostgreSQL client on EC2, then run `init.sql`:
```bash
sudo dnf install -y postgresql15
psql -h <rds-endpoint> -U ty -d devproject -f init.sql
```

Note: you may see a warning about psql major version 15 vs server major version 18 — this is harmless for basic operations.

If you didn't set an initial database name during RDS setup, the `devproject` database won't exist yet. Create it first:
```bash
psql -h <rds-endpoint> -U ty -d postgres
```
```sql
CREATE DATABASE devproject;
\q
```
Then run `init.sql` as above.

### 9. Start the App
```bash
cd ~/phase3
docker compose up --build -d
docker compose ps       # both containers should be Up
docker compose logs -f  # tail logs to verify no errors
```

### 10. Test End-to-End
Update `SERVER_URL` in your local `phase3/client.py`:
```python
SERVER_URL = "http://<ec2-public-ip>/message"   # Elastic IP if you allocated one
```
Run the client locally:
```bash
python3 phase3/client.py
```
Verify rows appear in RDS (run in EC2 Instance Connect terminal):
```bash
psql -h <rds-endpoint> -U ty -d devproject -c 'SELECT * FROM messages;'
```

---

## Tear Down
In EC2 Instance Connect terminal:
```bash
cd ~/<your-repo>/phase3 && docker compose down
```

Then in the AWS Console (to avoid ongoing charges):
1. Disassociate and release the Elastic IP (if allocated)
2. Terminate the EC2 instance
3. Delete the RDS instance (skip final snapshot for a PoC)
4. Delete the DB subnet group (`dev-project-db-subnet-group`)
5. Delete `ec2-sg` and `rds-sg`
6. Delete the VPC (`dev-project-vpc`) — this also removes its subnets, route tables, and IGW

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
