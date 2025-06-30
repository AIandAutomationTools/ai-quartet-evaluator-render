from flask import Flask, request, jsonify
import threading
import requests
import os
import librosa
import numpy as np
import soundfile as sf

app = Flask(__name__)

# Utility to download MP3 files from Google Drive direct links
def download_file(url, filename):
    try:
        response = requests.get(url)
        if response.status_code == 200:
            with open(filename, "wb") as f:
                f.write(response.content)
            print(f"Downloaded {filename}")
        else:
            raise Exception(f"Failed to download file: {url}")
    except Exception as e:
        raise Exception(f"Download error: {e}")

# Utility to extract pitch and timing features
def extract_pitch_timing(audio_path):
    try:
        y, sr = librosa.load(audio_path, sr=None)
        pitches, magnitudes = librosa.piptrack(y=y, sr=sr)
        pitch = np.mean(pitches[pitches > 0]) if np.any(pitches > 0) else 0.0
        tempo, _ = librosa.beat.beat_track(y=y, sr=sr)
        return pitch, tempo
    except Exception as e:
        print(f"Audio analysis error: {e}")
        return 0.0, 0.0

# Background processing task
def process_student_submission(data):
    try:
        student_url = data["student_url"]
        professor_url = data["professor_url"]
        callback_url = data["callback_url"]
        student_email = data.get("student_email", "unknown")

        # Download files
        download_file(student_url, "student.mp3")
        download_file(professor_url, "professor.mp3")

        # Extract pitch and timing
        student_pitch, student_tempo = extract_pitch_timing("student.mp3")
        professor_pitch, professor_tempo = extract_pitch_timing("professor.mp3")

        # Compare values
        pitch_diff = abs(student_pitch - professor_pitch)
        timing_diff = abs(student_tempo - professor_tempo)

        # Prepare result
        result = {
            "student_email": student_email,
            "score": max(0, 100 - (pitch_diff * 10 + timing_diff * 5)),  # basic scoring
            "pitch_difference": round(pitch_diff, 2),
            "timing_difference": round(timing_diff, 2)
        }

        # Callback to Zapier
        response = requests.post(callback_url, json=result)
        print(f"Sent results to Zapier. Status: {response.status_code}")
    except Exception as e:
        print(f"Processing failed: {e}")

@app.route("/submit", methods=["POST"])
def submit():
    data = request.get_json()
    threading.Thread(target=process_student_submission, args=(data,)).start()
    return jsonify({"status": "received", "message": "Evaluation started."}), 200

@app.route("/", methods=["GET"])
def home():
    return "AI Quartet Evaluator is running.", 200

if __name__ == "__main__":
    app.run(debug=True, port=5000)

