import os
import json
import librosa
import matplotlib.pyplot as plt
import requests
import numpy as np
from b2sdk.v2 import InMemoryAccountInfo, B2Api
from b2sdk.v2.exception import InvalidAuthToken

# === Load environment variables ===
print("🔄 Loading environment variables...")

B2_KEY_ID = os.getenv("B2_KEY_ID")
B2_APPLICATION_KEY = os.getenv("B2_APPLICATION_KEY")
B2_BUCKET_NAME = os.getenv("B2_BUCKET_NAME")
CLIENT_PAYLOAD_RAW = os.getenv("CLIENT_PAYLOAD")

print(f"🔍 Env debug:")
print(f"✅ B2_KEY_ID: {B2_KEY_ID}")
print(f"✅ B2_BUCKET_NAME: {B2_BUCKET_NAME}")
print(f"✅ B2_APPLICATION_KEY length: {len(B2_APPLICATION_KEY) if B2_APPLICATION_KEY else 'None'}")
print(f"📦 Raw Payload: {CLIENT_PAYLOAD_RAW}")

if not B2_KEY_ID or not B2_APPLICATION_KEY or not B2_BUCKET_NAME or not CLIENT_PAYLOAD_RAW:
    print("❌ ERROR: One or more required environment variables are missing!")
    exit(1)

# === Parse client_payload ===
try:
    payload = json.loads(CLIENT_PAYLOAD_RAW)
    callback_url = payload["callback_url"]
    professor_url = payload["professor_url"]
    student_url = payload["student_url"]
    student_email = payload["student_email"]
except Exception as e:
    print("❌ Error parsing client_payload")
    print(e)
    exit(1)

# === Download MP3 files ===
def download_file(url, filename):
    print(f"⬇️ Downloading {url}...")
    response = requests.get(url)
    if response.status_code != 200:
        raise Exception(f"Failed to download {url}")
    with open(filename, "wb") as f:
        f.write(response.content)
    print(f"✅ Saved to {filename}")

download_file(professor_url, "professor.mp3")
download_file(student_url, "student.mp3")

# === Load audio and compute pitch ===
print("🎼 Extracting pitch...")
prof_y, _ = librosa.load("professor.mp3")
stud_y, _ = librosa.load("student.mp3")

prof_pitch = librosa.yin(prof_y, fmin=librosa.note_to_hz('C2'), fmax=librosa.note_to_hz('C7'))
stud_pitch = librosa.yin(stud_y, fmin=librosa.note_to_hz('C2'), fmax=librosa.note_to_hz('C7'))

# === Calculate pitch and timing difference ===
min_len = min(len(prof_pitch), len(stud_pitch))
pitch_diff = float(np.mean(np.abs(prof_pitch[:min_len] - stud_pitch[:min_len])))
timing_diff = abs(len(prof_pitch) - len(stud_pitch)) / len(prof_pitch)

print(f"🎯 Pitch difference: {pitch_diff:.2f} Hz")
print(f"⏱️ Timing difference: {timing_diff:.2%}")

# === Create pitch comparison graph ===
graph_filename = "output_graph.png"
plt.figure(figsize=(10, 4))
plt.plot(prof_pitch[:min_len], label="Professor", alpha=0.7)
plt.plot(stud_pitch[:min_len], label="Student", alpha=0.7)
plt.legend()
plt.title("Pitch Comparison")
plt.xlabel("Time Frame")
plt.ylabel("Frequency (Hz)")
plt.tight_layout()
plt.savefig(graph_filename)
print(f"🖼️ Graph saved as {graph_filename}")

# === Upload to Backblaze B2 ===
try:
    print("🔐 Authorizing with B2...")
    info = InMemoryAccountInfo()
    b2_api = B2Api(info)
    b2_api.authorize_account("production", B2_KEY_ID, B2_APPLICATION_KEY)
    bucket = b2_api.get_bucket_by_name(B2_BUCKET_NAME)

    b2_filename = f"{student_email}_graph.png"
    print(f"📤 Uploading {graph_filename} to B2 as {b2_filename}...")
    bucket.upload_local_file(
        local_file=graph_filename,
        file_name=b2_filename,
    )
    download_url = f"https://f000.backblazeb2.com/file/{B2_BUCKET_NAME}/{b2_filename}"
    print(f"✅ Upload complete. URL: {download_url}")

    # === Send callback to Zapier ===
    payload_to_zapier = {
        "student_email": student_email,
        "graph_url": download_url,
        "pitch_difference": round(pitch_diff, 2),
        "timing_difference": round(timing_diff, 2)
    }

    print(f"📡 Sending result to Zapier: {callback_url}")
    response = requests.post(callback_url, json=payload_to_zapier)
    print(f"✅ Callback status: {response.status_code}")
    print(f"📬 Response: {response.text}")

except InvalidAuthToken as e:
    print("❌ Auth error:", e)
    exit(1)
except Exception as e:
    print("❌ Error:", e)
    exit(1)
