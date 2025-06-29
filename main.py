from flask import Flask, request, jsonify
import requests
import librosa
import numpy as np
import os
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

app = Flask(__name__)

# Set your Google Drive folder ID (create one and copy the ID from the URL)
DRIVE_FOLDER_ID = 'your_google_drive_folder_id_here'
SERVICE_ACCOUNT_FILE = 'service_account.json'  # Upload this file to Render

SCOPES = ['https://www.googleapis.com/auth/drive.file']

def download_file(url, filename):
    url = url.strip()  # remove extra spaces
    print(f"🌐 Downloading from: {url}")
    response = requests.get(url)
    if response.status_code != 200:
        raise Exception(f"Failed to download file: {url}")
    with open(filename, 'wb') as f:
        f.write(response.content)
    print(f"📁 {filename} saved ({len(response.content)} bytes)")

def compare_audio(student_file, professor_file):
    y_student, sr_student = librosa.load(student_file, sr=None)
    y_professor, sr_professor = librosa.load(professor_file, sr=None)

    # Trim both to the same length
    min_len = min(len(y_student), len(y_professor))
    y_student = y_student[:min_len]_]()

