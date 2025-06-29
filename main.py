import os
import json
import requests
import librosa
import matplotlib.pyplot as plt

from flask import Flask, request, jsonify
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

# ─── Flask Setup ────────────────────────────────────────────────────────
app = Flask(__name__)

# ─── Google Drive Service ───────────────────────────────────────────────
def get_drive_service():
    try:
        service_account_info = json.loads(os.environ["GOOGLE_SERVICE_ACCOUNT_JSON"])
        if "private_key" in service_account_info:
            service_account_info["private_key"] = service_account_info["private_key"].replace("\\n", "\n")
        credentials = service_account.Credentials.from_service_account_info(service_account_info)
        return build("drive", "v3", credentials=credentials)
    except Exception as e:
        print("❌ Failed to load service account:", e)
        raise

drive_service = get_drive_service()

# ─── Routes ─────────────────────────────────────────────────────────────
@app.route("/", methods=["GET"])
def hello():
    return "✅ AI Quartet Evaluator API is running."

@app.route("/evaluate", methods=["POST"])
def evaluate():
    try:
        data = request.json
        email = data.get("email")
        student_url = data.get("student_url")
        professor_url = data.get("professor_url")

        if not email or not student_url or not professor_url:
            return jsonify({"error": "Missing fields"}), 400

        # Step 1: Download files
        student_file = download_audio(student_url, "student.mp3")
        professor_file = download_audio(professor_url, "professor.mp3")

        # Step 2: Generate graph
        graph_path = f"comparison_{email}.png"
        create_pitch_graph(student_file, professor_file, graph_path)

        # Step 3: Upload to Google Drive
        graph_url = upload_to_drive(drive_service, graph_path, "1TX5Z_wwQIvQKEqFFygd43SSQxYQZrD6k")

        # Step 4: Return analysis
        return jsonify({
            "email": email,
            "student_url": student_url,
            "professor_url": professor_url,
            "graph_url": graph_url,
            "analysis": "Student pitch was compared to professor. Check graph for alignment.",
            "status": "Evaluation complete"
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ─── Utilities ──────────────────────────────────────────────────────────
def download_audio(url, filename):
    response = requests.get(url)
    if response.status_code == 200:
        with open(filename, "wb") as f:
            f.write(response.content)
        return filename
    else:
        raise Exception(f"Failed to download file from: {url}")

def create_pitch_graph(student_file, professor_file, graph_path):
    student_audio, sr = librosa.load(student_file, sr=None)
    professor_audio, _ = librosa.load(professor_file, sr=sr)

    max_len = min(len(student_audio), len(professor_audio), sr * 10)  # Limit to 10s
    plt.figure(figsize=(12, 4))
    plt.plot(student_audio[:max_len], label="Student", alpha=0.7)
    plt.plot(professor_audio[:max_len], label="Professor", alpha=0.7)
    plt.legend()
    plt.title("Waveform Comparison (First 10 seconds)")
    plt.xlabel("Time (samples)")
    plt.ylabel("Amplitude")
    plt.tight_layout()
    plt.savefig(graph_path)
    plt.close()

def upload_to_drive(service, file_path, folder_id):
    file_metadata = {
        "name": os.path.basename(file_path),
        "parents": [folder_id]
    }
    media = MediaFileUpload(file_path, mimetype="image/png")
    uploaded = service.files().create(body=file_metadata, media_body=media, fields="id").execute()
    file_id = uploaded.get("id")
    return f"https://drive.google.com/uc?id={file_id}"

# ─── Run Locally (for testing) ──────────────────────────────────────────
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
