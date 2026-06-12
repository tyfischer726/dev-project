# dev-project

A simple client-server-database app for learning purposes. Type a message in the terminal, the client sends it to a Flask server via HTTP, the server logs it to PostgreSQL and returns a response.

## Stack

- Python 3.14, Flask, Gunicorn, nginx
- PostgreSQL 18
- Docker, Docker Compose
- Kubernetes (minikube)
- Terraform (AWS IaC)
- AWS (EC2 t2.micro, RDS PostgreSQL)
- GitHub Actions (CI: pytest + flake8)
- Claude Code

## Running with Docker

All Docker files live in `phase2/`. This runs 4 containers: `db`, `server`, `nginx`, and `client`.

1. Create a `phase2/.env` file:
   ```
   DB_NAME=your_dbname
   DB_USER=your_username
   DB_HOST=db
   DB_PASSWORD=your_password
   ```
   > `DB_HOST` must be `db` (the Docker service name), not `localhost`.

2. Start the backend services:
   ```bash
   cd phase2
   docker compose up --build -d db server nginx
   ```

3. Run the client interactively:
   ```bash
   docker compose run --rm client
   ```

4. Stop everything when done:
   ```bash
   docker compose down
   ```
   To also wipe the database volume: `docker compose down -v`

**Useful commands:**
```bash
docker compose logs db                                              # view db logs
docker compose logs -f db                                          # follow db logs
docker compose exec db psql -U <user> -d <dbname> -c "SELECT * FROM messages;"  # query the DB
```

## Running locally (without Docker)

1. Create a `.env` file with your database credentials:
   ```
   DB_NAME=your_dbname
   DB_USER=your_username
   DB_HOST=localhost
   DB_PASSWORD=your_password
   ```

2. Activate the virtual environment and install dependencies:
   ```bash
   source ../environments/dev_env/bin/activate
   pip install -r requirements.txt
   ```

Start **gunicorn** in one terminal:
```bash
gunicorn --bind 0.0.0.0:8000 server:app
```

Start **nginx** in another terminal:
```bash
nginx -c /FULL_PATH_TO_FILE/nginx.conf
```

Start the **client** in another terminal:
```bash
python3 client.py
```

Stop nginx when done:
```bash
nginx -c /FULL_PATH_TO_FILE/nginx.conf -s stop
```

> For quick dev without nginx/gunicorn, `python3 server.py` still works (Flask on port 5000 directly).

## Testing

```bash
python3 -m pytest test_server.py -v    # 7 unit tests (no DB required)
python3 -m flake8 server.py client.py  # lint
```

CI runs both automatically on push via GitHub Actions.

## Running with Kubernetes (minikube)

All Kubernetes manifests live in `phase2-k8s/`. Requires minikube and kubectl.

1. Start minikube:
   ```bash
   minikube start
   ```

2. Build images directly into minikube's Docker daemon (no registry needed):
   ```bash
   cd phase2-k8s
   ./build-images.sh
   ```

3. Apply all manifests:
   ```bash
   kubectl apply -f secret.yaml
   kubectl apply -f db.yaml
   kubectl apply -f server.yaml
   kubectl apply -f nginx.yaml
   ```
   > You can also apply all at once with `kubectl apply -f phase2-k8s/`

4. Wait for pods to be ready:
   ```bash
   kubectl get pods -w
   ```
   The `server` pod waits for the DB automatically via an init container.

5. Run the client:
   ```bash
   kubectl run client --image=client:latest --image-pull-policy=Never -it --restart=Never --rm
   ```

6. Tear down:
   ```bash
   kubectl delete -f phase2-k8s/   # remove all k8s resources (including DB data)
   minikube stop                    # stop the cluster
   minikube delete                  # delete the cluster entirely
   ```
   > To preserve DB data, avoid `minikube delete` — it destroys the entire cluster including all persistent volumes. Instead, only delete the app resources and stop (don't delete) minikube:
   > ```bash
   > kubectl delete -f phase2-k8s/server.yaml
   > kubectl delete -f phase2-k8s/nginx.yaml
   > minikube stop
   > ```
   > Leave `db.yaml` and `secret.yaml` in place. On next startup, run `minikube start` then re-apply only `server.yaml` and `nginx.yaml` — images and DB data both survive `minikube stop`.

**Useful commands:**
```bash
kubectl get pods                                                              # find the db pod name
kubectl exec -it <db-pod-name> -- psql -U ty -d devproject -c "SELECT * FROM messages;"  # query the DB
```

**Key details:**
- `secret.yaml` must be applied before `db.yaml`/`server.yaml` since both reference `db-secret`
- `imagePullPolicy: Never` tells Kubernetes to use the locally-built image instead of pulling from Docker Hub
- nginx listens on port 80 internally; the client talks to it via the `nginx` ClusterIP service

## Running on AWS (EC2 + RDS)

The setup runs nginx + server as Docker Compose containers on a single EC2 t2.micro, with RDS PostgreSQL as the database. The local `client.py` connects to the EC2 public IP over the internet.

### Option A: Terraform (recommended)

All Terraform files live in `phase3/iac/`. Full instructions in `phase3/iac/IAC.md`.

```bash
cd phase3/iac
terraform init
terraform apply        # ~10–15 min; prints ec2_public_ip when done
# set EC2_IP in phase3/client.py, then:
python3 phase3/client.py

terraform destroy      # tear everything down when done
```

### Option B: Manual (AWS Console)

All files live in `phase3/`. Full step-by-step in `phase3/PHASE3.md`.

Resources are created via the AWS Console; Docker and the app are set up via EC2 Instance Connect (browser-based terminal in the Console).

## Database

PostgreSQL database configured via `.env`. Stores messages in a `messages (id, message, response, created_at)` table.

When running with Docker, data is stored in a named Docker volume (`phase2_postgres_data`) and persists across restarts. It is only deleted with `docker compose down -v`.

Services are split across two custom bridge networks for isolation: `db` is only reachable by `server` (via `app-backend-network`); `nginx` and `client` communicate with `server` over `app-frontend-network` and cannot reach `db` directly.
