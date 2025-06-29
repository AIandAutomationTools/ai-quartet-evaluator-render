from flask import Flask, request, jsonify
import requests
import librosa
import numpy as np
import matplotlib.pyplot as plt
import os
import soundfile as sf
from pydrive.auth import GoogleAuth
from pydrive.drive import GoogleDrive

app = Flask(__name__)

# === Google Drive Setup ===
gauth = GoogleAuth()
gauth.LocalWebserverAuth()
drive = GoogleDrive(gauth)

# === Constants ===
DRIVE_FOLDER_ID = '1TX5Z_wwQIvQKEqFFygd43SSQxYQZrD6k'

def download_file(url, filename):
    """Download MP3 from Google Drive direct URL"""
    response = requests.get(url.strip())
    if response.status_code == 200:
        with open(filename, 'wb') as f:
            f.write(response.content)
        print(f"📁 Saved: {filename} ({len(response.content)} bytes)")
        return True
    else:
        print(f"❌ Failed to download {url} — status {response.status_code}")
        return False

def upload_to_drive(local_path, drive_filename):
    """Upload file to specific Google Drive folder"""
    file_drive = drive.CreateFile({'title': drive_filename, 'parents': [{'id': DRIVE_FOLDER_ID}]})
    file_drive.SetContentFile(local_path)
    file_drive.Upload()
    return file_drive['alternateLink']

def compare_pitch(student_path, professor_path, graph_path):
    """Compare pitch of two audio files and generate overlay graph"""
    y_student, sr_student = librosa.load(student_path, sr=None)
    y_professor, sr_professor = librosa.load(professor_path, sr=None)

    # Convert to pitch curves
    pitches_student, _ = librosa.piptrack(y=y_student, sr=sr_student)
    pitches_prof, _ = librosa.piptrack(y=y_professor, sr=sr_professor)

    pitch_curve_student = np.max(pitches_student, axis=0)
    pitch_curve_prof = np.max(pitches_prof, axis=0)

    plt.figure(figsize=(12, 5))
    plt.plot(pitch_curve_student, label="Student", color='blue')
    plt.plot(pitch_curve_prof, label="Professor", color='red')
    plt.title("Pitch Comparison")
    plt.xlabel("Frame")
    plt.ylabel("Frequency (Hz)")
    plt.legend()
    plt.tight_layout()
    plt.savefig(graph_path)
    plt.close()

@app.route('/evaluate', methods=['POST'])
def evaluate():
    try:
        data = request.get_json()
        print(f"📥 Incoming request: {data}")

        email = data.get('email')
        student_url = data.get('student_url', '').strip()
        professor_url = data.get('professor_url', '').strip()

        if not all([email, student_url, professor_url]):
            return jsonify({'error': 'Missing input'}), 400

        # Download files
        if not download_file(student_url, 'student.mp3') or not download_file(professor_url, 'professor.mp3'):
            return jsonify({'error': 'Failed to download one or more MP3s'}), 400

        # Compare and generate graph
        graph_filename = f'pitch_comparison_{email.replace("@", "_at_")}.png'
        compare_pitch('student.mp3', 'professor.mp3', graph_filename)

        # Upload to Drive
        graph_url = upload_to_drive(graph_filename, graph_filename)

        return jsonify({
            'message': 'Student was mostly in tune.',
            'graph_url': graph_url
        }), 200

    except Exception as e:
        print(f"❌ Error: {e}")
        return jsonify({'error': str(e)}), 500



