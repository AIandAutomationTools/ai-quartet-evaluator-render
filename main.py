import os
import tempfile
import requests
from flask import Flask, request, jsonify
import librosa
import numpy as np
import soundfile as sf

app = Flask(__name__)

def download_file(url, filename):
    try:
        response = requests.get(url)
        if response.status_code == 200:
            with open(filename, 'wb') as f:
                f.write(response.content)
            return True
        else:
            print(f"Failed to download file: {url}")
            return False
    except Exception as e:
        print(f"Download error: {e}")
        return False

def compare_audio(student_file, professor_file):
    try:
        y_student, sr_student = librosa.load(student_file)
        y_professor, sr_professor = librosa.load(professor_file)

        min_len = min(len(y_student), len(y_professor))
        y_student = y_student[:min_len]
        y_professor = y_professor[:min_len]

        # Timing difference (cross-correlation)
        correlation = np.correlate(y_student, y_professor, mode='full')
        lag = correlation.argmax() - (len(y_professor) - 1)

        # Pitch difference
        student_pitch = librosa.yin(y_student, fmin=librosa.note_to_hz('C2'), fmax=librosa.note_to_hz('C7'))
        professor_pitch = librosa.yin(y_professor, fmin=librosa.note_to_hz('C2'), fmax=librosa.note_to_hz('C7'))
        pitch_diff = np.abs(np.mean(student_pitch) - np.mean(professor_pitch))

        return {
            "timing_lag_samples": int(lag),
            "pitch_difference": round(float(pitch_diff), 2)
        }
    except Exception as e:
        return {"error": str(e)}

@app.route('/process', methods=['POST'])
def process_audio():
    try:
        data = request.json
        student_url = data.get('student_url')
        professor_url = data.get('professor_url')

        if not student_url or not professor_url:
            return jsonify({"error": "Missing URLs"}), 400

        with tempfile.TemporaryDirectory() as tmpdirname:
            student_path = os.path.join(tmpdirname, "student.mp3")
            professor_path = os.path.join(tmpdirname, "professor.mp3")

            if not download_file(student_url, student_path):
                return jsonify({"error": "Failed to download student file"}), 400
            if not download_file(professor_url, professor_path):
                return jsonify({"error": "Failed to download professor file"}), 400

            result = compare_audio(student_path, professor_path)
            return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

