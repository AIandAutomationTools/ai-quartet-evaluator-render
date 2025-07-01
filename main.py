from flask import Flask, request, jsonify
import threading
import requests
import librosa
import numpy as np
import soundfile as sf
import os
import io
import json
import time
import matplotlib.pyplot as plt
from datetime import datetime
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

app = Flask(__name__)

UPLOAD_FOLDER = "downloads"
CHART_FOLDER = "static"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(CHART_FOLDER, exist_ok=True)

STUDENT_EVAL_FOLDER_ID = "1TX5Z_wwQIvQKEqFFygd43SSQxYQZrD6k"

# --- Google Drive Setup ---
def get_drive_service():
    sa_info = json.loads(os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON"))
    credentials = service_account.Credentials.from_service_account_info(
        sa_info, scopes=["https://www.googleapis.com/auth/drive"]
    )
    return build("drive", "v3", credentials=credentials)

# --- File Download ---
def download_file(url, filename):
    try:
        r = requests.get(url.strip())
        r.raise_for_status()
        with open(filename, "wb") as f:
            f.write(r.content)
        return True
    except Exception as e:
        print(f"Download error: {e}")
        return False

# --- Audio Comparison ---
def compare_audio(student_path, professor_path):
    y_student, sr_student = librosa.load(student_path)
    y_professor, sr_professor = librosa.load(professor_path)

    min_len = min(len(y_student), len(y_professor))
    y_student = y_student[:min_len]
    y_professor = y_professor[:min_len]

    chroma_student = librosa.feature.chroma_stft(y=y_student, sr=sr_student)
    chroma_professor = librosa.feature.chroma_stft(y=y_professor, sr=sr_professor)
    pitch_diff = np.mean(np.abs(chroma_student - chroma_professor))

    rms_student = librosa.feature.rms(y=y_student)[0]
    rms_professor = librosa.feature.rms(y=y_professor)[0]
    rms_diff = np.mean(np.abs(rms_student - rms_professor))

    return pitch_diff, rms_diff

# --- Google Drive Upload ---
def upload_to_drive(file_path, filename):
    try:
        service = get_drive_service()
        file_metadata = {'name': filename, 'parents': [STUDENT_EVAL_FOLDER_ID]}
        media = MediaFileUpload(file_path, resumable=True)
        file = service.files().create(body=file_metadata, media_body=media, fields='id').execute()
        return f"https://drive.google.com/uc?id={file.get('id')}"
    except Exception as e:
        print(f"Drive upload error: {e}")
        return "Upload failed."

# --- Chart Generation ---
def generate_chart(pitch_diff, timing_diff, timestamp):
    try:
        plt.figure(figsize=(4, 3))
        plt.bar(["Pitch", "Timing"], [pitch_diff, timing_diff], color=["#3498db", "#2ecc71"])
        plt.ylabel("Difference")
        plt.title("Audio Comparison")
        chart_path = os.path.join(CHART_FOLDER, f"chart_{timestamp}.png")
        plt.tight_layout()
        plt.savefig(chart_path)
        plt.close()
        return f"https://{os.getenv('RENDER_EXTERNAL_HOSTNAME')}/static/chart_{timestamp}.png"
    except Exception as e:
        print(f"Chart generation error: {e}")
        return "Upload failed."

# --- Main Evaluation Thread ---
def process_and_callback(data):
    try:
        student_url = data["student_url"].strip()
        professor_url = data["professor_url"].strip()
        email = data["student_email"]
        callback_url = data["callback_url"]

        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        student_path = os.path.join(UPLOAD_FOLDER, f"student_{timestamp}.mp3")
        professor_path = os.path.join(UPLOAD_FOLDER, f"professor_{timestamp}.mp3")

        if not download_file(student_url, student_path) or not download_file(professor_url, professor_path):
            requests.post(callback_url, json={"error": "File download failed", "student_email": email})
            return

        pitch_diff, timing_diff = compare_audio(student_path, professor_path)

        feedback_path = os.path.join(UPLOAD_FOLDER, f"feedback_{timestamp}.txt")
        with open(feedback_path, "w") as f:
            f.write(f"Pitch Difference: {round(pitch_diff, 2)}\n")
            f.write(f"Timing Difference: {round(timing_diff, 2)}\n")

        drive_url = upload_to_drive(feedback_path, os.path.basename(feedback_path))
        chart_url = generate_chart(pitch_diff, timing_diff, timestamp)

        response_data = {
            "student_email": email,
            "pitch_difference": float(round(pitch_diff, 2)),
            "timing_difference": float(round(timing_diff, 2)),
            "feedback_url": drive_url,
            "graph_url": chart_url
        }
        requests.post(callback_url, json=response_data)

        for f in [student_path, professor_path, feedback_path]:
            if os.path.exists(f):
                os.remove(f)

    except Exception as e:
        print(f"Processing error: {e}")
        if "callback_url" in data:
            requests.post(data["callback_url"], json={
                "error": str(e),
                "student_email": data.get("student_email", "")
            })

# --- Cleanup Old Charts ---
def cleanup_old_charts(directory="static", age_limit_hours=24):
    now = time.time()
    age_limit_seconds = age_limit_hours * 3600
    for filename in os.listdir(directory):
        path = os.path.join(directory, filename)
        if os.path.isfile(path) and now - os.path.getmtime(path) > age_limit_seconds:
            try:
                os.remove(path)
                print(f"Deleted: {path}")
            except Exception as e:
                print(f"Failed to delete {path}: {e}")

# --- Flask Routes ---
@app.route("/", methods=["GET"])
def index():
    return "AI Quartet Evaluator is running", 200

@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.get_json()
    if not data:
        return jsonify({"error": "Missing JSON data"}), 400
    threading.Thread(target=process_and_callback, args=(data,)).start()
    return jsonify({"status": "received", "student_email": data.get("student_email")}), 200

@app.route("/cleanup", methods=["POST"])
def cleanup_endpoint():
    try:
        cleanup_old_charts()
        return jsonify({"status": "Cleanup complete"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
