from flask import Flask, request, jsonify
import requests
import librosa
import numpy as np
import os

app = Flask(__name__)

@app.route('/analyze', methods=['POST'])
def analyze():
    try:
        data = request.get_json()
        email = data.get('email')
        student_url = data.get('student_url').strip()
        professor_url = data.get('professor_url').strip()

        # Download audio files
        student_path = 'student.mp3'
        professor_path = 'professor.mp3'
        download_file(student_url, student_path)
        download_file(professor_url, professor_path)

        # Load audio
        y_student, sr_student = librosa.load(student_path)
        y_professor, sr_professor = librosa.load(professor_path)

        # Trim to same length
        min_len = min(len(y_student), len(y_professor))
        y_student = y_student[:min_len]
        y_professor = y_professor[:min_len]

        # Compare pitch
        student_pitch = librosa.yin(y_student, fmin=librosa.note_to_hz('C2'), fmax=librosa.note_to_hz('C7'))
        professor_pitch = librosa.yin(y_professor, fmin=librosa.note_to_hz('C2'), fmax=librosa.note_to_hz('C7'))
        pitch_diff = np.abs(student_pitch - professor_pitch).mean()

        # Compare timing (tempo)
        tempo_student, _ = librosa.beat.beat_track(y=y_student, sr=sr_student)
        tempo_professor, _ = librosa.beat.beat_track(y=y_professor, sr=sr_professor)
        tempo_diff = abs(tempo_student - tempo_professor)

        # Feedback
        feedback = {
            "email": email,
            "pitch_difference": round(float(pitch_diff), 2)

