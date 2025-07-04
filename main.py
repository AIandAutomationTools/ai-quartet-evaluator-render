import os
import json
import librosa
import matplotlib.pyplot as plt
import requests
from urllib.parse import quote
from b2sdk.v2 import InMemoryAccountInfo, B2Api
from b2sdk.v2.exception import InvalidAuthToken

# === Load environment variables ===
print("🔄 Loading environment variables...")

B2_KEY_ID = os.getenv("B2_KEY_ID")
B2_APPLICATION_KEY = os.getenv("B2_APPLICATION_KEY")
B2_BUCKET_NAME = os.getenv("B2_BUCKET_NAME")
CLIENT_PAYLOAD_RAW = os.getenv("CLIENT_PAYLOAD")

print(f"\n🔍 Env debug:")
print(f"✅ B2_KEY_ID: {B2_KEY_ID}")
print(f"✅ B2_BUCKET_NAME: {B2_BUCKET_NAME}")
print(f"✅ B2_APPLICATION_KEY length: {len(B2_APPLICATION_KEY) if B2_APPLICATION_KEY else 'None'}")
print(f"📦 Raw Payload: {CLIENT_PAYLOAD_RAW}")

if not all([B2_KEY_ID, B2_APPLICATION_KEY, B2_BUCKET_NAME, CLIENT_PAYLOAD_RAW]):
    print("❌ ERROR: One or more required environment variables are missing!")
    exit(1)

# === Parse payload ===
try:
    payload = json.loads(CLIENT_PAYLOAD_RAW)
    callback_url = payload["callback_url"]
    professor_url = payload["professor_url"]
    student_url = payload["student_url"]
    student_email = payload["student_email"]
except Exception as e:
    print("❌ Error parsing payload:", e)
    exit(1)

# === Download audio files ===
def download_file(url, filename):
    print(f"⬇️ Downloading {url}...")
    r = requests.get(url)
    if r.status_code != 200:
        raise Exception(f"❌ Failed to download {url} → {r.status_code}")
    with open(filename, "wb") as f:
        f.write(r.content)
    print(f"✅ Saved to {filename}")

download_file(student_url, "student.mp3")
download_file(professor_url, "professor.mp3")

# === Analyze pitch ===
print("🎼 Extracting pitch...")
prof_y, sr = librosa.load("professor.mp3")
stud_y, _ = librosa.load("student.mp3")

prof_pitch = librosa.yin(prof_y, fmin=librosa.note_to_hz('C2'), fmax=librosa.note_to_hz('C7'))
stud_pitch = librosa.yin(stud_y, fmin=librosa.note_to_hz('C2'), fmax=librosa.note_to_hz('C7'))

# === Compute basic differences ===
pitch_diff = abs(prof_pitch.mean() - stud_pitch.mean())
timing_diff = abs(len(prof_pitch) - len(stud_pitch))

# === Generate graph ===
graph_filename = "output_graph.png"
plt.figure(figsize=(10, 4))
plt.plot(prof_pitch, label="Professor", alpha=0.7)
plt.plot(stud_pitch, label="Student", alpha=0.7)
plt.legend()
plt.title("Pitch Comparison")
plt.xlabel("Time Frame")
plt.ylabel("Frequency (Hz)")
plt.tight_layout()
plt.savefig(graph_filename)
print(f"✅ Graph saved: {graph_filename}")

# === Upload to Backblaze B2 ===
print("🔐 Authorizing with B2...")
try:
    info = InMemoryAccountInfo()
    b2_api = B2Api(info)
    b2_api.authorize_account("production", B2_KEY_ID, B2_APPLICATION_KEY)
    bucket = b2_api.get_bucket_by_name(B2_BUCKET_NAME)

    # Use email as part of the filename
    b2_filename = f"{student_email.replace('@', '_').replace('.', '_')}_graph.png"

    print(f"📤 Uploading {graph_filename} to B2 as {b2_filename}...")
    bucket.upload_local_file(
        local_file=graph_filename,
        file_name=b2_filename,
    )
    print("✅ Upload complete.")

    # === Generate signed temporary URL (1 hour) ===
    encoded_filename = quote(b2_filename)
    auth_token = b2_api.get_download_authorization(bucket.id_, b2_filename, 3600)
    download_url = f"https://f000.backblazeb2.com/file/{B2_BUCKET_NAME}/{encoded_filename}?Authorization={auth_token}"
    print(f"🌐 Download URL: {download_url}")

except Exception as e:
    print("❌ Upload error:", e)
    exit(1)

# === Send result to Zapier ===
payload_to_zapier = {
    "student_email": student_email,
    "graph_url": download_url,
    "pitch_difference": round(pitch_diff, 2),
    "timing_difference": timing_diff
}

print(f"📡 Sending result to Zapier: {callback_url}")
try:
    r = requests.post(callback_url, json=payload_to_zapier)
    print(f"✅ Callback status: {r.status_code}")
    print(f"📬 Response: {r.text}")
except Exception as e:
    print("❌ Callback failed:", e)
    exit(1)

