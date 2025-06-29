from flask import Flask, request, jsonify
import requests
import librosa
import numpy as np
import soundfile as sf
import os

app = Flask(__name__)

def download_file(url, filename):
    r = requests.get(url)
    with open(filename, 'wb') as f:
        f.write(r.content)
    return filename

def compare_audio(student_path, professor_path):
    y_student, sr_student = librosa.load(student_path)
    y_professor, sr_professor = librosa.load(professor_path)

    # Match length
    min_len = min(len(y_student), len(y_professor))
    y_student = y_student[:min_len]
    y_professor = y_professor[:min_len]

    # Compare pitch and timing
    pitch_student = librosa.yin(y_student, fmin=librosa.note_to_hz('C2'), fmax=librosa.note_to_hz('C7'))
    pitch_professor = librosa.yin(y_professor, fmin=librosa.note_to_hz('C2'), fmax=librosa.note_to_hz('C7'))

    pitch_diff = np.abs(np.mean(pitch_student) - np.mean(pitch_professor))

    timing_corr = np.corrcoef(y_student, y_professor)[0, 1]

    return pitch_diff, timing_corr

@app.route('/', methods=['POST'])
def evaluate():
    try:
        data = request.json
        email = data.get("email")
        student_url = data.get("student_url").strip()
        professor_url = data.get("professor_url").strip()

        download_file(student_url, "student.mp3")
        download_file(professor_url, "professor.mp3"
