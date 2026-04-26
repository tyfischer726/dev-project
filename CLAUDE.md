# dev-project

## Overview
A simple client-server-database app for learning purposes. The user types a message in the terminal, the client sends it to the server via HTTP, the server logs it to PostgreSQL and returns a response, and the client prints the response.

## Architecture
- **client.py** — terminal UI; sends POST requests to the server and prints responses
- **server.py** — Flask HTTP server; receives messages, logs them to the DB, returns a response
- **PostgreSQL** — stores every message + response in the `messages` table

## Stack
- Python 3.14
- Flask (HTTP server)
- requests (HTTP client)
- psycopg2-binary (PostgreSQL driver)
- python-dotenv (env var loading)
- PostgreSQL 18 (local)

## Environment
- Virtual env: `../environments/dev_env/` (relative to project root)
- Activate: `source ../environments/dev_env/bin/activate` (then use `python3` normally)
- Install packages via: `pip install ...` (when venv is active) or `/home/ty/Desktop/code/environments/dev_env/bin/python3 -m pip install ...`
- Dependencies tracked in `requirements.txt`

## Database
- Name: `devproject`
- User: `ty`
- Host: `localhost` (TCP) — password auth via `DB_PASSWORD` env var
- Table: `messages (id, message, response, created_at)`
- Credentials stored in `.env` (gitignored)

## Running locally
Activate the venv first (once per terminal session):
```bash
source ../environments/dev_env/bin/activate
```

Start the server in one terminal:
```bash
python3 server.py
```

Start the client in another terminal:
```bash
python3 client.py
```

## Future: Docker
Plan is to containerize into 3 containers:
- `client` — runs client.py
- `server` — runs server.py (Flask on port 5000)
- `db` — PostgreSQL

When containerized, the server's DB connection will use the container service name (e.g. `host="db"`) instead of `localhost`, and the client's SERVER_URL will point to the server container.
