from flask import Flask, request, jsonify
import threading
import requests
import librosa
import numpy as np
import os
import json
import matplotlib.pyplot as plt
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from datetime import datetime

app = Flask(__name__)
UPLOAD_FOLDER = "downloads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

STUDENT_EVAL_FOLDER_ID = "1TX5Z_wwQIvQKEqFFygd43SSQxYQZrD6k"

def get_drive_service():
    sa_info = json.loads(os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON"))
    credentials = service_account.Credentials.from_service_account_info(
        sa_info, scopes=["https://www.googleapis.com/auth/drive"]
    )
    return build("drive", "v3", credentials=credentials)

def upload_to_drive(file_path, filename):
    try:
        service = get_drive_service()
        file_metadata = {'name': filename, 'parents': [STUDENT_EVAL_FOLDER_ID]}
        media = MediaFileUpload(file_path, resumable=True)
        file = service.files().create(
            body=file_metadata, media_body=media, fields='id'
        ).execute()
        file_id = file.get('id')
        if file_id:
            print(f"✅ Uploaded {filename} to Drive with ID: {file_id}")
            return f"https://drive.google.com/uc?id={file_id}"
        else:
            print("⚠️ Upload failed: No file ID returned.")
            return None
    except Exception as e:
        print(f"❌ Drive upload error: {e}")
        return None

def download_file(url, filename):
    try:
        r = requests.get(url.strip())
        r.raise_for_status()
        with open(filename, "wb") as f:
            f.write(r.content)
        print(f"✅ Downloaded {filename}")
        return True
    except Exception as e:
        print(f"❌ Download error: {e}")
        return False

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

    return pitch_diff, timing_diff, rms_student, rms_professor

def create_comparison_plot(rms_student, rms_professor, filename):
    try:
        plt.figure(figsize=(10, 4))
        plt.plot(rms_student, label='Student', alpha=0.7)
        plt.plot(rms_professor, label='Professor', alpha=0.7)
        plt.title('Timing Comparison (RMS Energy)')
        plt.xlabel('Frame')
        plt.ylabel('RMS')
        plt.legend()
        plt.tight_layout()
        plt.savefig(filename)
        plt.close()
        print(f"✅ Graph saved as {filename}")
    except Exception as e:
        print(f"❌ Graph generation error: {e}")

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

        pitch_diff, timing_diff, rms_student, rms_professor = compare_audio(student_path, professor_path)

        # Text Feedback
        feedback_text = (
            f"Pitch Difference: {round(float(pitch_diff), 2)}\n"
            f"Timing Difference: {round(float(timing_diff), 2)}\n"
        )
        feedback_path = f"{UPLOAD_FOLDER}/feedback_{timestamp}.txt"
        with open(feedback_path, "w") as f:
            f.write(feedback_text)

        # Graph
        graph_path = f"{UPLOAD_FOLDER}/graph_{timestamp}.png"
        create_comparison_plot(rms_student, rms_professor, graph_path)

        feedback_url = upload_to_drive(feedback_path, os.path.basename(feedback_path))
        graph_url = upload_to_drive(graph_path, os.path.basename(graph_path))

        result = {
            "student_email": email,
            "pitch_difference": float(round(pitch_diff, 2)),
            "timing_difference": float(round(timing_diff, 2)),
            "feedback_url": feedback_url,
            "graph_url": graph_url
        }

        print(f"📤 Sending result to callback: {result}")
        requests.post(callback_url, json=result)

        for f in [student_path, professor_path, feedback_path, graph_path]:
            if os.path.exists(f):
                os.remove(f)

    except Exception as e:
        print(f"❌ Processing error: {e}")
        if "callback_url" in data:
            requests.post(data["callback_url"], json={
                "error": str(e),
                "student_email": data.get("student_email", "")
            })

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

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)


