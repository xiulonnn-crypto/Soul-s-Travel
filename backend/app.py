from dotenv import load_dotenv
load_dotenv()
from flask import Flask
from flask_cors import CORS
from database import init_db
from routes.trips import trips_bp
from routes.stats import stats_bp
from routes.share import share_bp
from routes.parse import parse_bp
from routes.evaluation import evaluation_bp
from routes.profile import profile_bp

app = Flask(__name__)
CORS(app)
app.register_blueprint(trips_bp)
app.register_blueprint(stats_bp)
app.register_blueprint(share_bp)
app.register_blueprint(parse_bp)
app.register_blueprint(evaluation_bp)
app.register_blueprint(profile_bp)


@app.route("/api/health")
def health():
    return {"status": "ok"}


if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=5001, debug=True)
