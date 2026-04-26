import os
import psycopg2
from flask import Flask, request, jsonify
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

def get_db():
    return psycopg2.connect(
        dbname="devproject",
        user="ty",
        password=os.environ["DB_PASSWORD"],
        host="localhost"
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
