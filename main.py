from flask import Flask, request, jsonify
import librosa
import librosa.display
import matplotlib.pyplot as plt
import tempfile
import requests
import os
import base64
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
import io

app = Flask(__name__)

# Google Drive setup
GDRIVE_CREDS = {
    "type": os.environ["GDRIVE_TYPE"],
    "project_id": os.environ["GDRIVE_PROJECT_ID"],
    "private_key_id": os.environ["GDRIVE_PRIVATE_KEY_ID"],
    "private_key": os.environ["GDRIVE_PRIVATE_KEY"].replace("\\n", "\n"),
    "client_email": os.environ["GDRIVE_CLIENT_EMAIL"],
    "client_id": os.environ["GDRIVE_CLIENT_ID"],
    "auth_uri": os.environ["GDRIVE_AUTH_URI"],
    "token_uri": os.environ["GDRIVE_TOKEN_URI"],
    "auth_provider_x509_cert_url": os.environ["GDRIVE_AUTH_PROVIDER_CERT"],
    "client_x509_cert_url": os.environ["GDRIVE_CLIENT_CERT_URL"]
}
IMG_API_KEY = os.environ["IMGBB_API_KEY"]

credentials = service_account.Credentials.from_service_account_info(GDRIVE_CREDS)
drive_service = build("drive", "v3", credentials=credentials)

def download_from_drive(url):
    file_id = url.split("/d/")[1].split("/")[0]
    request = drive_service.files().get_media(fileId=file_id)
    fh = io.BytesIO()
    downloader = MediaIoBaseDownload(fh, request)
    done = False
    while not done:
        _, done = downloader.next_chunk()
    fh.seek(0)
    return fh

def extract_pitch(audio_file):
    y, sr = librosa.load(audio_file, sr=None)
    pitches, _ = librosa.piptrack(y=y, sr=sr)
    return [max(p) for p in pitches.T if max(p) > 0]

def create_plot(prof_pitch, stud_pitch, student_email):
    plt.figure(figsize=(14, 5))
    plt.plot(prof_pitch, label='Professor', alpha=0.75)
    plt.plot(stud_pitch, label='Student', alpha=0.75)
    plt.legend()
    plt.title("Pitch Comparison")
    image_file = f"{student_email}_plot.png"
    plt.savefig(image_file)
    plt.close()
    return image_file

def upload_to_imgbb(image_path):
    with open(image_path, "rb") as f:
        encoded = base64.b64encode(f.read())
    payload = {
        "key": IMG_API_KEY,
        "image": encoded
    }
    r = requests.post("https://api.imgbb.com/1/upload", data=payload)
    return r.json()['data']['url']

@app.route("/evaluate", methods=["POST"])
def evaluate():
    data = request.json
    email = data.get("email")
    student_url = data.get("student_url")
    prof_url = data.get("prof_url")

    try:
        # Download files
        student_audio = download_from_drive(student_url)
        professor_audio = download_from_drive(prof_url)

        with tempfile.NamedTemporaryFile(suffix=".wav") as tmp1, \
             tempfile.NamedTemporaryFile(suffix=".wav") as tmp2:

            tmp1.write(student_audio.read())
            tmp1.flush()
            tmp2.write(professor_audio.read())
            tmp2.flush()

            spitch = extract_pitch(tmp1.name)
            ppitch = extract_pitch(tmp2.name)

        # Create image
        plot_file = create_plot(ppitch, spitch, email)
        image_url = upload_to_imgbb(plot_file)

        # Basic comparison result
        score = min(len(spitch), len(ppitch))
        pitch_diff = sum(abs(a - b) for a, b in zip(spitch[:score], ppitch[:score])) / score
        evaluation = "Good pitch match!" if pitch_diff < 50 else "Significant pitch variation detected."

        # Return to Zapier
        return jsonify({
            "status": "success",
            "student_email": email,
            "image_url": image_url,
            "evaluation": evaluation
        })

    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500

if __name__ == "__main__":
    app.run()
