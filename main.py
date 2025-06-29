from flask import Flask, request, jsonify
import requests
import librosa
import numpy as np
import soundfile as sf
import os

app = Flask(__name__)

def download_file(url, filename):
    response = requests.get(url, stream=True)
    if response.status_code == 200:
        with open(filename, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
    else:
        raise Exception(f"Failed to download file: {url}")

def analyze_audio(student_path, professor_path):
    # Load audio files
    y_student, sr_student = librosa.load(student_path)
    y_professor, sr_professor = librosa.load(professor_path)

    # Ensure sample rates match
    if sr_student != sr_professor:
        raise Exception("Sample rates do not match")

    # Trim to the shorter length
    min_len = min(len(y_student), len(y_professor))
    y_student = y_student[:min_len]
    y_professor = y_professor[:min_len]

    # Pitch analysis (estimate fundamental frequency)
    f0_student, _, _ = librosa.pyin(y_student, fmin=librosa.note_to_hz('C2'), fmax=librosa.note_to_hz('C7'))
    f0_professor, _, _ = librosa.pyin(y_professor, fmin=librosa.note_to_hz('C2'), fmax=librosa.note_to_hz('C7'))

    # Remove NaNs and pad with median if necessary
    f0_student = np.nan_to_num(f0_student, nan=np.nanmedian(f0_student))
    f0_professor = np.nan_to_num(f0_professor, nan=np.nanmedian(f0_professor))

    pitch_diff = np.mean(np.abs(f0_student - f0_professor))

    # Timing analysis (onset)
    onsets_student = librosa.onset.onset_detect(y_student, sr=sr_student)
    onsets_professor = librosa.onset.onset_detect(y_professor, sr=sr_professor)

    timing_diff = np.abs(np.mean(onsets_student) - np.mean(onsets_professor))

    return {
        "pitch_difference": round(float(pitch_diff), 2),
        "timing_difference": round(float(timing_diff), 2)
    }

@app.route("/", methods=["POST"])
def evaluate():
    try:
        data = request.get_json()
        email = data.get("email")
        student_url = data.get("student_url", "").strip()
        professor_url = data.get("professor_url", "").strip()

        if not student_url or not professor_url:
            return jsonify({"error": "Missing URLs"}), 400

        download_file(student_url, "student.mp3")
    except Exception as e:
        return jsonify({"error": f"Failed to download student file: {str(e)}"}), 500

    try:
        download_file(professor_url, "professor.mp3")
    except Exception as e:
        return jsonify({"error": f"Failed to download professor file: {str(e)}"}), 500

    try:
        result = analyze_audio("student.mp3", "professor.mp3")
    except Exception as e:
        return jsonify({"error": f"Audio analysis failed: {str(e)}"}), 500

    return jsonify({
        "email": email,
        "result": result
    })

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
