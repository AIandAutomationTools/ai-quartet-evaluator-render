import os
import json
from flask import Flask, request, jsonify
from google.oauth2 import service_account
from googleapiclient.discovery import build

app = Flask(__name__)

# Load and parse service account credentials
service_account_info = json.loads(os.environ["GOOGLE_SERVICE_ACCOUNT_JSON"])
credentials = service_account.Credentials.from_service_account_info(service_account_info)

# Initialize Drive service (if needed)
drive_service = build("drive", "v3", credentials=credentials)

@app.route("/", methods=["GET"])
def index():
    return "AI Quartet Evaluator API is running."

@app.route("/evaluate", methods=["POST"])
def evaluate():
    try:
        data = request.get_json()
        email = data.get("email")
        student_url = data.get("student_url")
        professor_url = data.get("professor_url")

        if not all([email, student_url, professor_url]):
            return jsonify({"error": "Missing fields"}), 400

        # TODO: Add Deepgram + comparison logic here

        return jsonify({
            "email": email,
            "student_url": student_url,
            "professor_url": professor_url,
            "status": "Evaluation complete (mock)",
            "visual_graph_url": "https://example.com/mock-graph.png"
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)


