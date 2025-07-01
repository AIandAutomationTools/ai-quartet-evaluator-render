from flask import Flask, request, jsonify
import threading
import requests
import librosa
import numpy as np
import soundfile as sf
import os
import io
import json
import matplotlib.pyplot as plt
import datetime
import uuid
import b2sdk.v2 as b2

app = Flask(__name__)
UPLOAD_FOLDER = "downloads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Initialize B2 client
def get_b2_bucket():
    info = b2.InMemoryAccountInfo()
    b2_api = b2.B2Api(info)
    b2_api.authorize_account(
        "production",
        os.getenv("B2_KEY_ID"),
        os.getenv("B2_APP_KEY")
    )
    return b2_api.get_bucket_by_name(os.getenv("B2_BUCKET_NAME"))

# Upload a file to B2
def upload_to_b2(filepath, filename):
    try:
        bucket = get_b2_bucket()
        with open(filepath, 'rb') as file:
            b2_file = bucket.upload_bytes(file.read(), filename)
            return f"https://f000.backblazeb2.com/file/{bucket.name}/{filename}"
    except Exception as e:
        print(f"B2 Upload error: {e}")
        return None

# Download an audio file
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

# Generate comparison metrics and chart
def compare_audio(student_path, professor_path, graph_path):
    y1, sr1 = librosa.load(student_path)
    y2, sr2 = librosa.load(professor_path)

    min_len = min(len(y1), len(y2))
    y1, y2 = y1[:min_len], y2[:min_len]

    pitch_diff = float(np.mean(np.abs(librosa.feature.chroma_stft(y=y1, sr=sr1) -
                                      librosa.feature.chroma_stft(y=y2, sr=sr2))))
    rms_diff = float(np.mean(np.abs(librosa.feature.rms(y=y1)[0] -
                                    librosa.feature.rms(y=y2)[0])))

    # Plot and save graph
    plt.figure(figsize=(10, 4))
    plt.plot(y1, label='Student', alpha=0.7)
    plt.plot(y2, label='Professor', alpha=0.7)
    plt.title('Audio Waveform Comparison')
    plt.legend()
    plt.tight_layout()
    plt.savefig(graph_path)
    plt.close()

    return round(pitch_diff, 2), round(rms_diff, 2)

# Process webhook payload
def process_and_callback(data):
    try:
        student_url = data["student_url"].strip()
        professor_url = data["professor_url"].strip()
        email = data["student_email"]
        callback_url = data["callback_url"]

        timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
        student_path = os.path.join(UPLOAD_FOLDER, f"student_{timestamp}.mp3")
        professor_path = os.path.join(UPLOAD_FOLDER, f"professor_{timestamp}.mp3")
        feedback_path = os.path.join(UPLOAD_FOLDER, f"feedback_{timestamp}.txt")
        graph_path = os.path.join(UPLOAD_FOLDER, f"graph_{timestamp}.png")

        if not (download_file(student_url, student_path) and download_file(professor_url, professor_path)):
            requests.post(callback_url, json={"error": "File download failed", "student_email": email})
            return

        pitch_diff, timing_diff = compare_audio(student_path, professor_path, graph_path)

        with open(feedback_path, "w") as f:
            f.write(f"Pitch Difference: {pitch_diff}\nTiming Difference: {timing_diff}")

        feedback_url = upload_to_b2(feedback_path, os.path.basename(feedback_path)) or "Upload failed."
        graph_url = upload_to_b2(graph_path, os.path.basename(graph_path)) or "Upload failed."

        result = {
            "student_email": email,
            "pitch_difference": pitch_diff,
            "timing_difference": timing_diff,
            "feedback_url": feedback_url,
            "graph_url": graph_url
        }
        requests.post(callback_url, json=result)

    except Exception as e:
        print(f"Error: {e}")
        if "callback_url" in data:
            requests.post(data["callback_url"], json={"error": str(e), "student_email": data.get("student_email")})
    finally:
        for f in [student_path, professor_path, feedback_path, graph_path]:
            if os.path.exists(f):
                os.remove(f)

@app.route("/", methods=["GET"])
def index():
    return "AI Quartet Evaluator (Backblaze B2 Version) is live", 200

@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.get_json()
    if not data:
        return jsonify({"error": "Missing JSON data"}), 400
    threading.Thread(target=process_and_callback, args=(data,)).start()
    return jsonify({"status": "received", "student_email": data.get("student_email")}), 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)

