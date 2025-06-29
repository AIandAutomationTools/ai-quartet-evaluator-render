import os
import json
from flask import Flask, request, jsonify
from google.oauth2 import service_account
from googleapiclient.discovery import build

app = Flask(__name__)

# Load credentials from env var (minified JSON)
def get_drive_service():
    try:
        service_account_info = json.loads(os.environ["GOOGLE_SERVICE_ACCOUNT_JSON"])
        # Fix the escaped newlines in private_key
        if "private_key" in service_account_info:
            service_account_info["private_key"] = service_account_info["private_key"].replace("\\n", "\n")

        credentials = service_account.Credentials.from_service_account_info(service_account_info)
        return build("drive", "v3", credentials=credentials)
    except Exception as e:
        print("❌ Failed to load service account:", e)
        raise

drive_service = get_drive_service()

@app.route("/", methods=["GET"])
def hello():
    return "✅ AI Quartet Evaluator API is running."

@app.route("/evaluate", methods=["POST"])
def evaluate():
    try:
        data = request.json
        student_email = data.get("email")
        student_audio_url = data.get("student_url")
        professor_audio_url = data.get("professor_url")

        if not student_email or not student_audio_url or not professor_audio_url:
            return jsonify({"error": "Missing fields"}), 400

        # Placeholder for Deepgram and evaluation logic
        result = {
            "email": student_email,
            "student_url": student_audio_url,
            "professor_url": professor_audio_url,
            "graph_url": "https://yourdomain.com/waveform.png",  # Placeholder
            "analysis": "Student was mostly in tune.",
            "status": "Evaluation complete"
        }
        return jsonify(result)

    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))

