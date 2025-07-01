from flask import Flask, request, jsonify
import threading
import requests
import librosa
import numpy as np
import matplotlib.pyplot as plt
import os
import json
from datetime import datetime
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

app = Flask(__name__)

UPLOAD_FOLDER = "downloads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

STUDENT_EVAL_FOLDER_ID = "1TX5Z_wwQIvQKEqFFygd43SSQxYQZrD6k"

# Authenticate Google Drive service using environment variable
def get_drive_service():
    try:
        sa_raw = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON")
        if not sa_raw:
            print("[ERROR] GOOGLE_SERVICE_ACCOUNT_JSON is empty or missing!")
            return None

        sa_info = json.loads(sa_raw)
        print("[INFO] Successfully loaded GOOGLE_SERVICE_ACCOUNT_JSON")

        credentials = service_account.Credentials.from_service_account_info(
            sa_info, scopes=["https://www.googleapis.com/auth/drive"]
        )
        return build("drive", "v3", credentials=credentials)
    except Exception as e:
        print(f"[ERROR] Failed to parse GOOGLE_SERVICE_ACCOUNT_JSON: {e}")
        return None

def download_file(url, filename):
    try:
        r = requests.get(url.strip())
        r.raise_for_status()
        with open(filename, "wb") as f:
            f.write(r.content)
        print(f"[INFO] Downloaded: {filename}")
        return True
    except Exception as e:
        print(f"[ERROR] Download failed for {url}: {e}")
        return False

def compare_audio(student_path, professor_path):
    y_student, sr_student = librosa.load(student_path)
    y_professor, sr_professor = librosa.load(professor_path)

    min_len = min(len(y_student), len(y_professor))
    y_student = y_student[:min_len]
    y_professor = y_professor[:min_len]

    chroma_student = librosa.feature.chroma_stft(y=y_student, sr=sr_student)
    chroma

