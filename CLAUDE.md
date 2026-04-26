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
- PostgreSQL 18 (local)

## Environment
- Virtual env: `../environments/dev_env/` (relative to project root)
- Always run Python via: `/home/ty/Desktop/code/environments/dev_env/bin/python3`
- Install packages via: `/home/ty/Desktop/code/environments/dev_env/bin/python3 -m pip install ...`

## Database
- Name: `devproject`
- User: `ty` (OS peer auth, no password)
- Host: Unix socket (no host specified) — uses OS peer auth, no password needed locally
- Table: `messages (id, message, response, created_at)`

## Running locally
Start the server in one terminal:
```bash
/home/ty/Desktop/code/environments/dev_env/bin/python3 server.py
```

Start the client in another terminal:
```bash
/home/ty/Desktop/code/environments/dev_env/bin/python3 client.py
```

## Future: Docker
Plan is to containerize into 3 containers:
- `client` — runs client.py
- `server` — runs server.py (Flask on port 5000)
- `db` — PostgreSQL

When containerized, the server's DB connection will use the container service name (e.g. `host="db"`) instead of `localhost`, and the client's SERVER_URL will point to the server container.
