import os
import threading
import requests
import librosa
import numpy as np
import soundfile as sf
import matplotlib.pyplot as plt
from flask import Flask, request, jsonify
from datetime import datetime
from b2sdk.v2 import InMemoryAccountInfo, B2Api

# === B2 Setup ===
B2_KEY_ID = os.getenv("B2_KEY_ID")
B2_APP_KEY = os.getenv("B2_APP_KEY")
B2_BUCKET_NAME = os.getenv("B2_BUCKET_NAME")

info = InMemoryAccountInfo()
b2_api = B2Api(info)
b2_api.authorize_account("production", B2_KEY_ID, B2_APP_KEY)
bucket = b2_api.get_bucket_by_name(B2_BUCKET_NAME)

# === Flask App ===
app = Flask(__name__)
UPLOAD_FOLDER = "downloads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# === Helper Functions ===
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

    return pitch_diff, rms_diff, y_student, y_professor, sr_student

def save_waveform_plot(y1, y2, sr, filename):
    plt.figure(figsize=(10, 4))
    plt.plot(y1, label='Student', alpha=0.7)
    plt.plot(y2, label='Professor', alpha=0.7)
    plt.title('Audio Comparison')
    plt.legend()
    plt.tight_layout()
    plt.savefig(filename)
    plt.close()

def upload_to_b2(file_path, file_name):
    try:
        with open(file_path, "rb") as f:
            b2_file = bucket.upload_bytes(f.read(), file_name)
        url = bucket.get_download_url(file_name, valid_duration_in_seconds=86400)  # 24 hours
        return url
    except Exception as e:
        print(f"B2 upload error: {e}")
        return "Upload failed."

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

        pitch_diff, timing_diff, y_student, y_professor, sr = compare_audio(student_path, professor_path)

        # Save feedback
        result_txt = f"Pitch Difference: {round(float(pitch_diff), 2)}\nTiming Difference: {round(float(timing_diff), 2)}\n"
        feedback_path = f"{UPLOAD_FOLDER}/feedback_{timestamp}.txt"
        with open(feedback_path, "w") as f:
            f.write(result_txt)

        # Save graph
        graph_path = f"{UPLOAD_FOLDER}/graph_{timestamp}.png"
        save_waveform_plot(y_student, y_professor, sr, graph_path)

        # Upload files
        feedback_url = upload_to_b2(feedback_path, os.path.basename(feedback_path))
        graph_url = upload_to_b2(graph_path, os.path.basename(graph_path))

        result = {
            "student_email": email,
            "pitch_difference": float(round(pitch_diff, 2)),
            "timing_difference": float(round(timing_diff, 2)),
            "feedback_url": feedback_url,
            "graph_url": graph_url
        }
        requests.post(callback_url, json=result)

        for f in [student_path, professor_path, feedback_path, graph_path]:
            if os.path.exists(f):
                os.remove(f)

    except Exception as e:
        print(f"Processing error: {e}")
        if "callback_url" in data:
            requests.post(data["callback_url"], json={"error": str(e), "student_email": data.get("student_email", "")})

@app.route("/", methods=["GET"])
def index():
    return "AI Quartet Evaluator with Backblaze B2 is running", 200

@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.get_json()
    if not data:
        return jsonify({"error": "Missing JSON data"}), 400

    threading.Thread(target=process_and_callback, args=(data,)).start()
    return jsonify({"status": "received", "student_email": data.get("student_email")}), 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)

