from flask import Flask, request, jsonify
import requests
import librosa
import numpy as np
import os
import json
from datetime import datetime
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
import matplotlib.pyplot as plt

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

def download_file(url, filename):
    try:
        r = requests.get(url.strip())
        r.raise_for_status()
        with open(filename, "wb") as f:
            f.write(r.content)
        return True
    except Exception as e:
        print(f"[ERROR] Download failed: {e}")
        return False

def compare_audio(student_path, professor_path):
    y_student, sr_student = librosa.load(student_path, sr=22050, duration=30.0)
    y_professor, sr_professor = librosa.load(professor_path, sr=22050, duration=30.0)

    min_len = min(len(y_student), len(y_professor))
    y_student = y_student[:min_len]
    y_professor = y_professor[:min_len]

    chroma_student = librosa.feature.chroma_stft(y=y_student, sr=sr_student)
    chroma_professor = librosa.feature.chroma_stft(y=y_professor, sr=sr_professor)
    pitch_diff = np.mean(np.abs(chroma_student - chroma_professor))

    rms_student = librosa.feature.rms(y=y_student)[0]
    rms_professor = librosa.feature.rms(y=y_professor)[0]
    timing_diff = np.mean(np.abs(rms_student - rms_professor))

    return pitch_diff, timing_diff, rms_student, rms_professor

def generate_chart(student_rms, professor_rms, output_path):
    try:
        plt.figure(figsize=(10, 4))
        plt.plot(student_rms, label='Student RMS', alpha=0.75)
        plt.plot(professor_rms, label='Professor RMS', alpha=0.75)
        plt.title('Timing Comparison')
        plt.xlabel('Frame')
        plt.ylabel('RMS Energy')
        plt.legend()
        plt.tight_layout()
        plt.savefig(output_path)
        plt.close()
    except Exception as e:
        print(f"[ERROR] Chart generation failed: {e}")

def upload_to_drive(file_path, filename):
    try:
        service = get_drive_service()
        file_metadata = {
            'name': filename,
            'parents': [STUDENT_EVAL_FOLDER_ID]
        }
        media = MediaFileUpload(file_path, resumable=False)
        uploaded_file = service.files().create(
            body=file_metadata, media_body=media, fields="id"
        ).execute()
        return f"https://drive.google.com/uc?id={uploaded_file.get('id')}"
    except Exception as e:
        print(f"[ERROR] Upload to Drive failed: {e}")
        return None

def process_and_callback(data):
    student_path = professor_path = feedback_path = chart_path = None
    try:
        student_url = data["student_url"].strip()
        professor_url = data["professor_url"].strip()
        email = data["student_email"]
        callback_url = data["callback_url"]

        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        student_path = f"{UPLOAD_FOLDER}/student_{timestamp}.mp3"
        professor_path = f"{UPLOAD_FOLDER}/professor_{timestamp}.mp3"
        feedback_path = f"{UPLOAD_FOLDER}/feedback_{timestamp}.txt"
        chart_path = f"{UPLOAD_FOLDER}/chart_{timestamp}.png"

        if not download_file(student_url, student_path) or not download_file(professor_url, professor_path):
            requests.post(callback_url, json={"error": "File download failed", "student_email": email})
            return

        pitch_diff, timing_diff, rms_student, rms_professor = compare_audio(student_path, professor_path)

        # Save feedback
        feedback_text = (
            f"Pitch Difference: {round(float(pitch_diff), 2)}\n"
            f"Timing Difference: {round(float(timing_diff), 2)}"
        )
        with open(feedback_path, "w") as f:
            f.write(feedback_text)

        # Generate and upload chart
        generate_chart(rms_student, rms_professor, chart_path)

        feedback_url = upload_to_drive(feedback_path, os.path.basename(feedback_path))
        chart_url = upload_to_drive(chart_path, os.path.basename(chart_path))

        result = {
            "student_email": email,
            "pitch_difference": round(float(pitch_diff), 2),
            "timing_difference": round(float(timing_diff), 2),
            "feedback_url": feedback_url or "Upload failed",
            "chart_url": chart_url or "Upload failed"
        }

        requests.post(callback_url, json=result)

    except Exception as e:
        print(f"[ERROR] Processing error: {e}")
        if "callback_url" in data:
            requests.post(data["callback_url"], json={
                "error": str(e),
                "student_email": data.get("student_email", "")
            })
    finally:
        for f in [student_path, professor_path, feedback_path, chart_path]:
            if f and os.path.exists(f):
                os.remove(f)

@app.route("/", methods=["GET"])
def index():
    return "AI Quartet Evaluator is running", 200

@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.get_json()
    if not data:
        return jsonify({"error": "Missing JSON data"}), 400

    # You can switch back to threading.Thread(...) if needed
    process_and_callback(data)
    return jsonify({"status": "processing", "student_email": data.get("student_email")}), 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)

