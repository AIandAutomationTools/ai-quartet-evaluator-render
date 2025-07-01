import os
import io
import json
import requests
import librosa
import numpy as np
import soundfile as sf
import matplotlib.pyplot as plt
from flask import Flask, request, jsonify
import threading
from datetime import datetime
from b2sdk.v2 import InMemoryAccountInfo, B2Api

# Flask setup
app = Flask(__name__)
UPLOAD_FOLDER = "downloads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Backblaze B2 credentials (set in Render as env variables)
B2_KEY_ID = os.getenv("B2_KEY_ID")
B2_APP_KEY = os.getenv("B2_APP_KEY")
B2_BUCKET_NAME = os.getenv("B2_BUCKET_NAME")

# Authenticate B2
info = InMemoryAccountInfo()
b2_api = B2Api(info)
b2_api.authorize_account("production", B2_KEY_ID, B2_APP_KEY)
bucket = b2_api.get_bucket_by_name(B2_BUCKET_NAME)


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

    return pitch_diff, rms_diff, rms_student, rms_professor


def generate_chart(student_rms, professor_rms, out_path):
    plt.figure(figsize=(10, 4))
    plt.plot(student_rms, label="Student RMS", color="blue")
    plt.plot(professor_rms, label="Professor RMS", color="orange")
    plt.title("Volume Comparison")
    plt.xlabel("Frame")
    plt.ylabel("RMS")
    plt.legend()
    plt.tight_layout()
    plt.savefig(out_path)
    plt.close()


def upload_to_b2(file_path, file_name):
    try:
        with open(file_path, "rb") as f:
            file_info = {"uploaded": datetime.now().isoformat()}
            bucket.upload_bytes(f.read(), file_name, file_infos=file_info)
        file_url = f"https://f000.backblazeb2.com/file/{B2_BUCKET_NAME}/{file_name}"
        return file_url
    except Exception as e:
        print(f"B2 Upload error: {e}")
        return None


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

        pitch_diff, timing_diff, student_rms, professor_rms = compare_audio(student_path, professor_path)

        feedback_text = (
            f"Pitch Difference: {round(float(pitch_diff), 2)}\n"
            f"Timing Difference: {round(float(timing_diff), 2)}\n"
        )
        feedback_path = f"{UPLOAD_FOLDER}/feedback_{timestamp}.txt"
        with open(feedback_path, "w") as f:
            f.write(feedback_text)

        chart_path = f"{UPLOAD_FOLDER}/chart_{timestamp}.png"
        generate_chart(student_rms, professor_rms, chart_path)

        feedback_url = upload_to_b2(feedback_path, os.path.basename(feedback_path)) or "Upload failed."
        chart_url = upload_to_b2(chart_path, os.path.basename(chart_path)) or "Upload failed."

        result = {
            "student_email": email,
            "pitch_difference": float(round(pitch_diff, 2)),
            "timing_difference": float(round(timing_diff, 2)),
            "feedback_url": feedback_url,
            "graph_url": chart_url,
        }
        requests.post(callback_url, json=result)

        for f in [student_path, professor_path, feedback_path, chart_path]:
            if os.path.exists(f):
                os.remove(f)

    except Exception as e:
        print(f"Processing error: {e}")
        if "callback_url" in data:
            requests.post(data["callback_url"], json={"error": str(e), "student_email": data.get("student_email", "")})


@app.route("/", methods=["GET"])
def index():
    return "AI Quartet Evaluator with B2 is running", 200


@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.get_json()
    if not data:
        return jsonify({"error": "Missing JSON data"}), 400

    threading.Thread(target=process_and_callback, args=(data,)).start()
    return jsonify({"status": "received", "student_email": data.get("student_email")}), 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 10000)))
