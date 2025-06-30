from flask import Flask, request, jsonify
import requests, os
import librosa
import numpy as np
import soundfile as sf
import matplotlib.pyplot as plt
from pydrive.auth import GoogleAuth
from pydrive.drive import GoogleDrive

app = Flask(__name__)

# Authenticate Google Drive
def authenticate_drive():
    gauth = GoogleAuth()
    gauth.LoadCredentialsFile("service_account.json")
    gauth.LocalWebserverAuth()
    drive = GoogleDrive(gauth)
    return drive

# Download MP3
def download_file(url, filename):
    r = requests.get(url)
    r.raise_for_status()
    with open(filename, 'wb') as f:
        f.write(r.content)

# Generate waveform image
def generate_waveform(mp3_path, output_img):
    y, sr = librosa.load(mp3_path)
    plt.figure(figsize=(10, 4))
    librosa.display.waveshow(y, sr=sr)
    plt.title('Waveform')
    plt.tight_layout()
    plt.savefig(output_img)
    plt.close()

# Upload image to Google Drive
def upload_to_drive(filepath, folder_id):
    drive = authenticate_drive()
    file_drive = drive.CreateFile({'title': os.path.basename(filepath),
                                   'parents': [{'id': folder_id}]})
    file_drive.SetContentFile(filepath)
    file_drive.Upload()
    return f"https://drive.google.com/uc?id={file_drive['id']}"

# Analyze audio
def analyze_audio(student_file, professor_file):
    y_s, sr_s = librosa.load(student_file)
    y_p, sr_p = librosa.load(professor_file)
    min_len = min(len(y_s), len(y_p))
    y_s = y_s[:min_len]
    y_p = y_p[:min_len]
    pitch_s = librosa.yin(y_s, fmin=librosa.note_to_hz('C2'), fmax=librosa.note_to_hz('C7'))
    pitch_p = librosa.yin(y_p, fmin=librosa.note_to_hz('C2'), fmax=librosa.note_to_hz('C7'))
    pitch_diff = np.mean(np.abs(pitch_s - pitch_p))
    onset_s = librosa.onset.onset_detect(y=y_s, sr=sr_s)
    onset_p = librosa.onset.onset_detect(y=y_p, sr=sr_p)
    timing_diff = np.mean(np.abs(onset_s - onset_p)) if len(onset_s) == len(onset_p) else -1
    return round(float(pitch_diff), 2), round(float(timing_diff), 2)

@app.route('/process', methods=['POST'])
def process():
    try:
        data = request.json
        student_url = data['student_url']
        professor_url = data['professor_url']
        student_email = data['student_email']

        # Download files
        download_file(student_url, "student.mp3")
        download_file(professor_url, "professor.mp3")

        # Analyze
        pitch, timing = analyze_audio("student.mp3", "professor.mp3")

        # Generate waveform & upload
        waveform_img = "waveform.png"
        generate_waveform("student.mp3", waveform_img)
        waveform_url = upload_to_drive(waveform_img, "1TX5Z_wwQIvQKEqFFygd43SSQxYQZrD6k")

        # Clean up
        os.remove("student.mp3")
        os.remove("professor.mp3")
        os.remove(waveform_img)

        # Return result
        return jsonify({
            "status": "success",
            "student_email": student_email,
            "analysis": {
                "pitch_difference": pitch,
                "timing_difference": timing
            },
            "waveform_url": waveform_url
        })

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == '__main__':
    app.run(host="0.0.0.0", port=10000)
