from flask import Flask, request, jsonify
import threading
import requests
import librosa
import numpy as np
import soundfile as sf
import os
import json
from datetime import datetime
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

app = Flask(__name__)

UPLOAD_FOLDER = "downloads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Replace this with your actual shared folder ID
STUDENT_EVAL_FOLDER_ID = "1TX5Z_wwQIvQKEqFFygd43SSQxYQZrD6k"

# --- Google Drive service using environment variable ---
def get_drive_service():
    try:
        sa_info = json.loads(os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON"))
        credentials = service_account.Credentials.from_service_account_info(
            sa_info, scopes=["https://www.googleapis.com/auth/drive"]
        )
        return build("drive", "v3", credentials=credentials)
    except Exception as e:
        print(f"❌ Google Drive auth failed: {e}")
        return None

# --- Download file from public URL ---
def download_file(url, filename):
    try:
        r = requests.get(url.strip())
        r.raise_for_status()
        with open(filename, "wb") as f:
            f.write(r.content)
        print(f"✅ Downloaded: {filename}")
        return True
    except Exception as e:
        print(f"❌ Download error: {e}")
        return False

# --- Compare two audio files ---
def compare_audio(student_path, professor_path):
    try:
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
    except Exception as e:
        print(f"❌ Audio comparison error: {e}")
        raise

# --- Upload feedback to Google Drive ---
def upload_to_drive(file_path, filename):
    try:
        print(f"🚀 Uploading to Google Drive: {file_path}")
        service = get_drive_service()
        if not service:
            raise Exception("Google Drive service unavailable")

        file_metadata = {
            'name': filename,
            'parents': [STUDENT_EVAL_FOLDER_ID]
        }
        media = MediaFileUpload(file_path, resumable=True)
        file = service.files().create(
            body=file_metadata, media_body=media, fields='id'
        ).execute()

        drive_url = f"https://drive.google.com/uc?id={file.get('id')}"
        print(f"✅ Upload successful: {drive_url}")
        return drive_url
    except Exception as e:
        print(f"❌ Drive upload error: {e}")
        return None

# --- Main processing thread ---
def process_and_callback(data):
    try:
        student_url = data["student_url"].strip()
        professor_url = data["professor_url"].strip()
        email = data["student_email"]
        callback_url = data["callback_url"]

        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        student_path = f"{UPLOAD_FOLDER}/student_{timestamp}.mp3"
        professor_path = f"{UPLOAD_FOLDER}/professor_{timestamp}.mp3"

        if not download_file(student_url, student_path) or not download_file(professor_url, professor_path):
            requests.post(callback_url, json={"error": "File download failed", "student_email": email})
            return

        pitch_diff, timing_diff = compare_audio(student_path, professor_path)

        feedback = (
            f"Pitch Difference: {round(float(pitch_diff), 2)}\n"
            f"Timing Difference: {round(float(timing_diff), 2)}\n"
        )
        feedback_path = f"{UPLOAD_FOLDER}/feedback_{timestamp}.txt"
        with open(feedback_path, "w") as f:
            f.write(feedback)

        drive_url = upload_to_drive(feedback_path, os.path.basename(feedback_path))

        result = {
            "student_email": email,
            "pitch_difference": float(round(pitch_diff, 2)),
            "timing_difference": float(round(timing_diff, 2)),
            "feedback_url": drive_url or "Upload failed"
        }
        requests.post(callback_url, json=result)

        for f in [student_path, professor_path, feedback_path]:
            if os.path.exists(f):
                os.remove(f)

    except Exception as e:
        print(f"❌ Processing error: {e}")
        if "callback_url" in data:
            requests.post(data["callback_url"], json={
                "error": str(e),
                "student_email": data.get("student_email", "")
            })

# --- Flask endpoints ---
@app.route("/", methods=["GET"])
def index():
    return "🎶 AI Quartet Evaluator is running 🎶", 200

@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.get_json()
    if not data:
        return jsonify({"error": "Missing JSON data"}), 400

    threading.Thread(target=process_and_callback, args=(data,)).start()
    return jsonify({"status": "received", "student_email": data.get("student_email")}), 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)

