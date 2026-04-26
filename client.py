import requests

SERVER_URL = "http://localhost:5000/message"

def send_message(message):
    resp = requests.post(SERVER_URL, json={"message": message})
    return resp.json()["response"]

if __name__ == "__main__":
    while True:
        message = input("Enter a message (or 'quit' to exit): ")
        if message.lower() == "quit":
            break
        print(send_message(message))
