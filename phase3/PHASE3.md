# Phase 3: AWS Deployment (ECS on EC2 + RDS)

## Context
Moving the phase2 Docker Compose app to AWS. Goal: nginx publicly accessible so the local client.py can reach it over the internet. ALB used initially to validate the architecture, then removed to save ~$16–20/month; replaced with an Elastic IP on the EC2 instance.

Tooling: AWS Console + CLI for this phase. Terraform is a planned future phase.

## Target Architecture

```
[Internet]
    |
[ALB] ← temporary, remove after validation
    | port 80
[EC2 t2.micro] (public subnet, ECS-optimized AMI)
  [ECS Task - bridge mode]
    ├── nginx container  (port 80 → host 80; links to "server")
    └── server container (port 8000, internal only)
         |
[RDS db.t3.micro - PostgreSQL] (private subnet)
```

After ALB teardown:
```
[Elastic IP] → [EC2 t2.micro:80] → nginx → server:8000 → RDS
```

## Files in phase3/

### Already copied (no edits yet)

| File | Source | Notes |
|------|--------|-------|
| `Dockerfile.server` | `phase2/Dockerfile.server` | No changes needed |
| `server.py` | `phase2/server.py` | No changes needed |
| `requirements.txt` | `phase2/requirements.txt` | No changes needed |
| `nginx.conf` | `phase2/nginx.conf` | No changes needed — `proxy_pass http://server:8000` works via ECS Docker link |
| `init.sql` | `phase2/init.sql` | Run against RDS to initialize schema |
| `client.py` | root `client.py` | `SERVER_URL` must be updated to ALB DNS or Elastic IP before use |

### Must be created from scratch

| File | Purpose |
|------|---------|
| `Dockerfile.nginx` | Bakes `nginx.conf` into the `nginx:alpine` image — ECS can't volume-mount local files |
| `task-definition.json` | ECS task definition: two containers (nginx + server), bridge mode, container link |
| `build-and-push.sh` | Builds both images and pushes to ECR |

### phase3/Dockerfile.nginx
```dockerfile
FROM nginx:alpine
COPY nginx.conf /etc/nginx/nginx.conf
```

### phase3/nginx.conf
Same as phase2/nginx.conf — no changes needed. `proxy_pass http://server:8000` works via the ECS Docker link.

### phase3/task-definition.json (skeleton)
```json
{
  "family": "dev-project",
  "networkMode": "bridge",
  "containerDefinitions": [
    {
      "name": "nginx",
      "image": "<account>.dkr.ecr.<region>.amazonaws.com/dev-project/nginx:latest",
      "portMappings": [{"containerPort": 80, "hostPort": 80, "protocol": "tcp"}],
      "links": ["server"],
      "memory": 128,
      "essential": true
    },
    {
      "name": "server",
      "image": "<account>.dkr.ecr.<region>.amazonaws.com/dev-project/server:latest",
      "portMappings": [{"containerPort": 8000, "protocol": "tcp"}],
      "memory": 384,
      "essential": true,
      "environment": [
        {"name": "DB_NAME", "value": "devproject"},
        {"name": "DB_USER", "value": "ty"},
        {"name": "DB_PASSWORD", "value": "<from RDS setup>"},
        {"name": "DB_HOST", "value": "<RDS endpoint hostname>"}
      ]
    }
  ]
}
```

### phase3/build-and-push.sh
```bash
#!/bin/bash
ACCOUNT=$(aws sts get-caller-identity --query Account --output text)
REGION=us-east-1
ECR=$ACCOUNT.dkr.ecr.$REGION.amazonaws.com

aws ecr get-login-password --region $REGION | docker login --username AWS --password-stdin $ECR

docker build -f Dockerfile.server -t dev-project/server ../phase2
docker tag dev-project/server:latest $ECR/dev-project/server:latest
docker push $ECR/dev-project/server:latest

docker build -f Dockerfile.nginx -t dev-project/nginx .
docker tag dev-project/nginx:latest $ECR/dev-project/nginx:latest
docker push $ECR/dev-project/nginx:latest
```

---

## Step-by-Step Deployment

### 1. ECR — Create Repositories
```bash
aws ecr create-repository --repository-name dev-project/server --region us-east-1
aws ecr create-repository --repository-name dev-project/nginx  --region us-east-1
```
Then run `build-and-push.sh`.

### 2. VPC & Networking (AWS Console or CLI)
- VPC: `10.0.0.0/16`
- Public subnet A: `10.0.1.0/24` (e.g., us-east-1a) — for EC2 + ALB
- Public subnet B: `10.0.2.0/24` (e.g., us-east-1b) — ALB requires 2 AZs
- Private subnet: `10.0.3.0/24` (e.g., us-east-1a) — for RDS
- Internet Gateway → attach to VPC
- Route table for public subnets: `0.0.0.0/0 → IGW`
- Private subnet route table: no IGW route

### 3. Security Groups
| SG | Inbound | Outbound |
|----|---------|----------|
| `alb-sg` | 80 from `0.0.0.0/0` | all |
| `ec2-sg` | 80 from `alb-sg`; 22 from your IP | all |
| `rds-sg` | 5432 from `ec2-sg` | all |

### 4. RDS — PostgreSQL
- Engine: PostgreSQL (free tier: db.t3.micro, 20 GiB gp2, single-AZ)
- DB name: `devproject`, user: `ty`
- Place in private subnet; assign `rds-sg`
- **Disable** public accessibility
- After creation, note the endpoint hostname → goes into task definition as `DB_HOST`
- Initialize schema: SSH into EC2 (step 5), then:
  ```bash
  psql -h <rds-endpoint> -U ty -d devproject -f init.sql
  ```

### 5. ECS Cluster + EC2
```bash
aws ecs create-cluster --cluster-name dev-project-cluster
```
Launch EC2 instance (Console):
- AMI: **Amazon ECS-Optimized Amazon Linux 2023** (search in AMI catalog)
- Instance type: `t2.micro`
- Subnet: public subnet A
- Security group: `ec2-sg`
- IAM instance profile: `ecsInstanceRole` (needs `AmazonEC2ContainerServiceforEC2Role` policy)
- User data to register with cluster:
  ```bash
  #!/bin/bash
  echo ECS_CLUSTER=dev-project-cluster >> /etc/ecs/ecs.config
  ```
- Key pair: create/select one for SSH access

Verify registration:
```bash
aws ecs list-container-instances --cluster dev-project-cluster
```

### 6. ECS Task Definition
Fill in `task-definition.json` with actual ECR URIs and RDS endpoint, then register:
```bash
aws ecs register-task-definition --cli-input-json file://phase3/task-definition.json
```

### 7. ALB (temporary)
- Type: Application Load Balancer, internet-facing
- Subnets: public subnet A + B
- Security group: `alb-sg`
- Target group: instance type, port 80, HTTP; health check path `/message`
- Listener: port 80 → target group
- Register EC2 instance as target

### 8. ECS Service
```bash
aws ecs create-service \
  --cluster dev-project-cluster \
  --service-name dev-project-svc \
  --task-definition dev-project \
  --desired-count 1 \
  --load-balancers "targetGroupArn=<tg-arn>,containerName=nginx,containerPort=80" \
  --launch-type EC2
```

### 9. Test End-to-End
- Get ALB DNS name from Console
- Update `client.py` `SERVER_URL` to `http://<alb-dns-name>/message`
- Run: `python3 client.py`
- Verify messages appear in RDS

### 10. Remove ALB (cost reduction)
After validation:
1. Delete ECS service, re-create without `--load-balancers`
2. Delete ALB listener, target group, then ALB
3. Allocate Elastic IP → associate with EC2 instance
4. Update `ec2-sg`: add inbound 80 from `0.0.0.0/0` (direct internet access)
5. Update `client.py` `SERVER_URL` to `http://<elastic-ip>/message`

---

## Critical Files

| File | Status | Role |
|------|--------|------|
| `phase3/Dockerfile.server` | copied | Server image — no changes needed |
| `phase3/server.py` | copied | Flask app — no changes needed |
| `phase3/requirements.txt` | copied | Python deps — no changes needed |
| `phase3/nginx.conf` | copied | nginx config — no changes needed |
| `phase3/init.sql` | copied | Run against RDS to initialize schema |
| `phase3/client.py` | copied | Update `SERVER_URL` to ALB DNS or Elastic IP |
| `phase3/Dockerfile.nginx` | **create** | Bakes nginx.conf into image |
| `phase3/task-definition.json` | **create** | Fill in ECR URIs + RDS endpoint |
| `phase3/build-and-push.sh` | **create** | Builds + pushes both images to ECR |

## Verification

1. `aws ecs list-tasks --cluster dev-project-cluster` → task running
2. `aws ecs describe-tasks ...` → both containers RUNNING, no exit codes
3. `curl http://<alb-dns>/message -X POST -H 'Content-Type: application/json' -d '{"message":"hello"}'` → JSON response
4. `python3 client.py` from local machine → interactive session works
5. SSH into EC2, `psql -h <rds> -U ty -d devproject -c 'SELECT * FROM messages;'` → rows present
