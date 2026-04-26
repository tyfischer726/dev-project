# dev-project

A simple client-server-database app for learning purposes. Type a message in the terminal, the client sends it to a Flask server via HTTP, the server logs it to PostgreSQL and returns a response.

## Stack

- Python 3.14, Flask, Gunicorn, nginx, psycopg2-binary, requests, python-dotenv
- PostgreSQL 18
- Claude Code

## Setup

1. Create a `.env` file with your database credentials:
   ```
   DB_NAME=your_dbname
   DB_USER=your_username
   DB_HOST=localhost
   DB_PASSWORD=your_password
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Running

Start **gunicorn** in one terminal:
```bash
gunicorn --bind 0.0.0.0:8000 server:app
```

Start **nginx** in another terminal:
```bash
nginx -c /home/ty/Desktop/code/dev-project/nginx.conf
```

Start the **client** in another terminal:
```bash
python3 client.py
```

Stop nginx when done:
```bash
nginx -c /home/ty/Desktop/code/dev-project/nginx.conf -s stop
```

> For quick dev without nginx/gunicorn, `python3 server.py` still works (Flask on port 5000 directly).

## Database

PostgreSQL database configured via `.env`. Stores messages in a `messages (id, message, response, created_at)` table.
