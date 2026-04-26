import os
import signal
import sys
import psycopg2
from flask import Flask, request, jsonify
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

# Register handlers for SIGHUP and SIGTERM so the process exits cleanly instead
# of lingering after the terminal is closed.
#
# SIGHUP is sent by the OS when the controlling terminal closes (e.g. you shut
# the terminal window without pressing Ctrl-C first). Some terminal emulators
# don't send it reliably, which is what causes the "port already in use" error
# the next time you try to start the server.
#
# SIGTERM is the standard "please stop" signal sent by tools like `kill` or
# process managers. Without a handler it would also leave the port occupied.
#
# Ctrl-C sends SIGINT, which Flask/Python already handles — no change needed there.
def _shutdown(sig, frame):
    sys.exit(0)

signal.signal(signal.SIGHUP, _shutdown)
signal.signal(signal.SIGTERM, _shutdown)

def get_db():
    return psycopg2.connect(
        dbname=os.environ["DB_NAME"],
        user=os.environ["DB_USER"],
        password=os.environ["DB_PASSWORD"],
        host=os.environ["DB_HOST"]
    )

@app.route("/message", methods=["POST"])
def receive_message():
    data = request.get_json()
    message = data.get("message", "")

    response = f"Server received: '{message}'"

    # Log the message and response to the database
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO messages (message, response) VALUES (%s, %s)",
        (message, response)
    )
    conn.commit()
    cur.close()
    conn.close()

    print(f"Logged to DB — message: '{message}'")
    return jsonify({"response": response})

if __name__ == "__main__":
    app.run(port=5000)
