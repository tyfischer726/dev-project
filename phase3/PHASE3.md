# Phase 3: AWS Deployment (EC2 + Docker Compose + RDS)

## Context
Moving the phase2 Docker Compose app to AWS. Goal: nginx publicly accessible via an Elastic IP so the local `client.py` can reach it over the internet. Single-instance proof of concept — no orchestration, no load balancer, no scaling. Uses EC2 + Docker Compose (reusing the phase2 setup) with RDS for the database.

Tooling: AWS Console for all resource creation. Terminal work (Docker install, git clone, docker compose) done via **EC2 Instance Connect** — the browser-based terminal in the AWS Console (EC2 → your instance → Connect → EC2 Instance Connect tab). No local AWS CLI or SSH needed.

## Architecture

```
dev-project-vpc (10.0.0.0/16)
├── public subnet 10.0.1.0/24 (AZ-a)
│     └── EC2 t2.micro ← Elastic IP (port 80)
│           [Docker Compose]
│             ├── nginx  (host 80 → container 80)
│             └── server (port 8000, internal only)
│                   |
├── private subnet A 10.0.2.0/24 (AZ-a)  ┐
└── private subnet B 10.0.3.0/24 (AZ-b)  ┘ DB subnet group
      └── RDS db.t3.micro (PostgreSQL, not publicly accessible)
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
**All local files are complete.** Next step: begin AWS setup at Step 1 (VPC & Networking).

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

**Add a route to the public subnet's route table:**
- VPC → Route Tables → find the route table associated with `dev-project-vpc`
- Routes tab → Edit routes → Add route: `0.0.0.0/0` → Target: `dev-project-igw`
- Subnet associations tab → Edit → associate `public-a`

(The two private subnets need no route table changes — RDS doesn't need internet access.)

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
| Inbound | 22 | My IP (EC2 Instance Connect fallback) |
| Outbound | all | `0.0.0.0/0` |

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

### 5. Elastic IP
Console: EC2 → Elastic IPs → Allocate Elastic IP address → Associate with your EC2 instance.

This is the permanent IP your `client.py` will point at.

### 6. Clone the Repo on EC2
In the EC2 Instance Connect terminal:
```bash
git clone https://github.com/<your-username>/<your-repo>.git
cd <your-repo>/phase3
```

### 7. Configure Environment on EC2
```bash
cp .env.template .env
nano .env   # fill in DB_PASSWORD and DB_HOST (the RDS endpoint)
```

### 8. Initialize RDS Schema
Install the PostgreSQL client on EC2, then run `init.sql`:
```bash
sudo dnf install -y postgresql15
psql -h <rds-endpoint> -U ty -d devproject -f ~/phase3/init.sql
```

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
SERVER_URL = "http://<elastic-ip>/message"
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
1. Disassociate and release the Elastic IP
2. Terminate the EC2 instance
3. Delete the RDS instance (skip final snapshot for a PoC)
4. Delete the DB subnet group (`dev-project-db-subnet-group`)
5. Delete `ec2-sg` and `rds-sg`
6. Delete the VPC (`dev-project-vpc`) — this also removes its subnets, route table, and IGW

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
