from flask import Flask, request, jsonify
import threading
import requests
import librosa
import numpy as np
import soundfile as sf
import os
import json
from datetime import datetime
from oauth2client.service_account import ServiceAccountCredentials
from pydrive.auth import GoogleAuth
from pydrive.drive import GoogleDrive

app = Flask(__name__)

# Google Drive setup using environment variable
credentials_json = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON")
if not credentials_json:
    raise Exception("GOOGLE_SERVICE_ACCOUNT_JSON environment variable not set")

creds_dict = json.loads(credentials_json)
gauth = GoogleAuth()
gauth.credentials = ServiceAccountCredentials.from_json_keyfile_dict(
    creds_dict, ["https://www.googleapis.com/auth/drive"]
)
drive = GoogleDrive(gauth)

UPLOAD_FOLDER = "downloads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

STUDENT_EVAL_FOLDER_ID = "1TX5Z_wwQIvQKEqFFygd43SSQxYQZrD6k"

def download_file(url, filename):
    try:
        r = requests.get(url)
        r.raise_for_status()
        with open(filename, "wb") as f:
            f.write(r.content)
        return True
    except Exception as e:
        print(f"Download error: {e}")
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

    return pitch_diff, rms_diff

def upload_to_drive(file_path):
    try:
        file = drive.CreateFile({
            'title': os.path.basename(file_path),
            'parents': [{'id': STUDENT_EVAL_FOLDER_ID}]
        })
        file.SetContentFile(file_path)
        file.Upload()
        return f"https://drive.google.com/uc?id={file['id']}"
    except Exception as e:
        print(f"Drive upload error: {e}")
        return None

def process_and_callback(data):
    try:
        student_url = data["student_url"]
        professor_url = data["professor_url"]
        email = data["student_email"]
        callback_url = data["callback_url"]

        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        student_path = f"{UPLOAD_FOLDER}/student_{timestamp}.mp3"
        professor_path = f"{UPLOAD_FOLDER}/professor_{timestamp}.mp3"

        if not download_file(student_url, student_path) or not download_file(professor_url, professor_path):
            requests.post(callback_url, json={"error": "File download failed", "student_email": email})
            return

        pitch_diff, timing_diff = compare_audio(student_path, professor_path)

        result_txt = f"Pitch Difference: {round(pitch_diff, 2)}\nTiming Difference: {round(timing_diff, 2)}\n"
        feedback_path = f"{UPLOAD_FOLDER}/feedback_{timestamp}.txt"
        with open(feedback_path, "w") as f:
            f.write(result_txt)

        drive_url = upload_to_drive(feedback_path)

        result = {
            "student_email": email,
            "pitch_difference": round(pitch_diff, 2),
            "timing_difference": round(timing_diff, 2),
            "feedback_url": drive_url
        }
        requests.post(callback_url, json=result)

        for f in [student_path, professor_path, feedback_path]:
            if os.path.exists(f):
                os.remove(f)

    except Exception as e:
        print(f"Processing error: {e}")
        if "callback_url" in data:
            requests.post(data["callback_url"], json={"error": str(e), "student_email": data.get("student_email")})

@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.get_json()
    if not data:
        return jsonify({"error": "Missing JSON data"}), 400

    threading.Thread(target=process_and_callback, args=(data,)).start()
    return jsonify({"status": "received", "student_email": data.get("student_email")}), 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
