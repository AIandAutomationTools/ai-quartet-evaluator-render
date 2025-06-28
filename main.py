from flask import Flask, request, jsonify
import os
import json
from google.oauth2 import service_account
from googleapiclient.discovery import build

app = Flask(__name__)

# Load Google credentials
service_account_info = json.loads(os.environ["GOOGLE_SERVICE_ACCOUNT_JSON"])
credentials = service_account.Credentials.from_service_account_info(service_account_info)

# Setup Drive
def setup_drive():
    return build("drive", "v3", credentials=credentials)

drive_service = setup_drive()

@app.route('/', methods=['POST'])
def evaluate_student():
    data = request.json
    student_email = data.get("email")
    student_url = data.get("student_url")
    professor_url = data.get("professor_url")

    if not all([student_email, student_url, professor_url]):
        return jsonify({"error": "Missing required fields."}), 400

    # Simulate evaluation logic here
    result = {
        "email": student_email,
        "student_url": student_url,
        "professor_url": professor_url,
        "status": "Evaluation complete (mock result)",
        "graph_url": "https://example.com/fake-graph.png"
    }

    return jsonify(result), 200

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=10000)
