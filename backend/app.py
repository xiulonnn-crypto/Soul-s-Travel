from flask import Flask
from flask_cors import CORS
from database import init_db

app = Flask(__name__)
CORS(app)


@app.route("/api/health")
def health():
    return {"status": "ok"}


if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=5001, debug=True)
