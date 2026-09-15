import os
from flask import Flask, jsonify
from sqlalchemy import create_engine, text

app = Flask(__name__)
STAND = os.getenv("STAND", "unknown")
DB_URL = os.getenv("DB_URL", "postgresql+psycopg2://appuser:apppass@localhost/appdb")
engine = create_engine(DB_URL)

@app.route("/")
def root():
    return jsonify(stand=STAND, status="ok")

@app.route("/db")
def db_check():
    with engine.connect() as conn:
        version = conn.execute(text("SELECT version()")).scalar()
    return jsonify(stand=STAND, postgres=version)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)