# Phase 3 — Terraform (IaC)

## Overview

Recreates the manual phase3 AWS deployment using Terraform. The infrastructure is identical — EC2 + RDS in a custom VPC — but all resource creation is automated via `.tf` files instead of console clicks. The EC2 instance also bootstraps itself on first boot via `user_data.sh`, replacing the manual Docker install and `docker compose up` steps done through EC2 Instance Connect.

## Architecture

```
dev-project-vpc (10.0.0.0/16)
├── public subnet 10.0.1.0/24 (us-east-1a)
│     └── EC2 t2.micro  ← auto-assigned public IP (port 80)
│           [Docker Compose — started by user_data.sh on first boot]
│             ├── nginx  (host 80 → container 80)
│             └── server (port 8000, internal only)
│
├── private subnet A 10.0.2.0/24 (us-east-1a)  ┐ DB subnet group
└── private subnet B 10.0.3.0/24 (us-east-1b)  ┘
      └── RDS db.t3.micro (PostgreSQL 17, not publicly accessible)
```

## Files

| File | Purpose |
|------|---------|
| `main.tf` | AWS provider and region |
| `variables.tf` | Input variables (`region`, `db_name`, `db_username`, `db_password`) |
| `terraform.tfvars` | Actual variable values — **gitignored**, never commit this |
| `vpc.tf` | VPC, 3 subnets, internet gateway, public route table, DB subnet group |
| `security_groups.tf` | `ec2-sg` (ports 80 + 22) and `rds-sg` (port 5432 from ec2-sg only) |
| `rds.tf` | RDS PostgreSQL instance in private subnets |
| `ec2.tf` | EC2 instance; renders `user_data.sh` via `templatefile()` |
| `user_data.sh` | Bootstrap script: Docker, git clone, `.env`, wait for RDS, `init.sql`, `docker compose up` |
| `outputs.tf` | Prints `ec2_public_ip` and `rds_endpoint` after apply |

## How `user_data.sh` works

Terraform's `templatefile()` renders `user_data.sh` before sending it to EC2, substituting `${db_host}`, `${db_name}`, `${db_username}`, and `${db_password}` with real values. The resulting script runs once automatically on first boot and:

1. Updates packages and installs Docker and git
2. Installs the Docker Compose plugin and Docker Buildx plugin
3. `git clone`s this repo to `/home/ec2-user/dev-project`
4. Writes `.env` into `phase3/` with the RDS credentials
5. Installs `postgresql15` client and polls `pg_isready` until RDS accepts connections
6. Runs `init.sql` to create the `messages` table
7. Runs `docker compose up --build -d`

Boot-to-ready takes roughly 10–15 minutes (dominated by RDS provisioning).

---

## Steps

### 1. Install Terraform (local, one-time)

```bash
sudo snap install terraform --classic
terraform version   # verify
```

### 2. Configure AWS credentials (local, one-time)

Terraform needs AWS credentials to create resources. This project uses IAM Identity Center (SSO).

If you don't have the AWS CLI:
```bash
sudo apt-get install -y awscli
```

Configure SSO (one-time setup):
```bash
aws configure sso
# SSO session name: dev (or anything)
# SSO start URL:    https://something.awsapps.com/start  (your portal URL)
# SSO region:       us-east-1
# Opens browser to authenticate — pick your account and permission set
# Default region:   us-east-1
# Output format:    json
# Profile name:     dev
```

Then log in:
```bash
aws sso login --profile dev
```

Set the profile for Terraform (repeat each terminal session):
```bash
export AWS_PROFILE=dev
```

> **Note:** SSO sessions expire (typically every 8–12 hours). Re-run `aws sso login --profile dev` when prompted.

### 3. Set your DB password

Edit `terraform.tfvars` and replace `REPLACE_ME` with a real password:

```
db_password = "your-password-here"
```

### 4. Initialize Terraform

Downloads the AWS provider plugin. Run once per machine (and again after any provider version change):

```bash
cd phase3/iac
terraform init
```

### 5. Deploy

```bash
terraform apply
```

Type `yes` when prompted. Takes ~10–15 minutes. When it finishes, Terraform prints:

```
ec2_public_ip = "x.x.x.x"
rds_endpoint  = "dev-project-db.xxxx.us-east-1.rds.amazonaws.com"
```

### 6. Wait for EC2 to finish bootstrapping

The EC2 instance is "running" within a minute, but `user_data.sh` is still installing Docker, waiting for RDS, and starting the app in the background. Give it **~10 minutes** from when `terraform apply` completes.

To watch the bootstrap log in real time via EC2 Instance Connect:
- AWS Console → EC2 → your instance → Connect → EC2 Instance Connect
```bash
sudo tail -f /var/log/cloud-init-output.log
```

### 7. Run the client

Copy the `ec2_public_ip` from step 5 into `phase3/client.py`:

```python
# phase3/client.py
EC2_IP = "x.x.x.x"
```

Then run:

```bash
python3 phase3/client.py
```

### 8. Tear down

```bash
terraform destroy
```

Type `yes`. Destroys all resources in reverse dependency order. Takes a few minutes.

---

## Notes

- **No Elastic IP** — the EC2 public IP changes on each fresh `terraform apply`. Update `EC2_IP` in `phase3/client.py` each time. Add an Elastic IP to `ec2.tf` if you want a stable address.
- **AMI filter** — `ec2.tf` uses the pattern `al2023-ami-2023*-x86_64` to select the standard Amazon Linux 2023 AMI. The broader pattern `al2023-ami-*-x86_64` also matches the minimal variant, which does not include `ec2-instance-connect` and will silently break EC2 Instance Connect.
- **`user_data.sh` template vars** — Terraform substitutes `${db_host}` etc. at apply time via `templatefile()`. Bash variables in the script use `$VAR` (no braces) to avoid conflicts with Terraform's syntax.
- **Bootstrap progress** — `user_data.sh` runs as root on first boot. Tail `/var/log/cloud-init-output.log` via EC2 Instance Connect to watch progress.
