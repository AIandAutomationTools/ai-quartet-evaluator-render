import os
import json
import requests
import librosa
import matplotlib.pyplot as plt
from b2sdk.v2 import InMemoryAccountInfo, B2Api
from b2sdk.v2.exception import InvalidAuthToken
from urllib.parse import quote

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

# === Download audio files ===
def download_file(url, filename):
    print(f"⬇️ Downloading {url}...")
    r = requests.get(url)
    if r.status_code != 200:
        print(f"❌ Failed to download {url}")
        exit(1)
    with open(filename, "wb") as f:
        f.write(r.content)
    print(f"✅ Saved to {filename}")

download_file(student_url, "student.mp3")
download_file(professor_url, "professor.mp3")

# === Extract pitch and compare ===
print("🎼 Extracting pitch...")
prof_y, _ = librosa.load("professor.mp3")
stud_y, _ = librosa.load("student.mp3")

prof_pitch = librosa.yin(prof_y, fmin=librosa.note_to_hz('C2'), fmax=librosa.note_to_hz('C7'))
stud_pitch = librosa.yin(stud_y, fmin=librosa.note_to_hz('C2'), fmax=librosa.note_to_hz('C7'))

# Pad shorter sequence for plotting
min_len = min(len(prof_pitch), len(stud_pitch))
prof_pitch = prof_pitch[:min_len]
stud_pitch = stud_pitch[:min_len]

# Dummy timing difference metric
timing_difference = abs(len(prof_y) - len(stud_y)) / 1000.0  # seconds
pitch_difference = float(abs(prof_pitch.mean() - stud_pitch.mean()))

# === Create graph ===
plt.figure(figsize=(10, 4))
plt.plot(prof_pitch, label="Professor", alpha=0.7)
plt.plot(stud_pitch, label="Student", alpha=0.7)
plt.legend()
plt.title("Pitch Comparison")
plt.xlabel("Frame")
plt.ylabel("Frequency (Hz)")
plt.tight_layout()
graph_filename = "output_graph.png"
plt.savefig(graph_filename)
print(f"✅ Graph saved: {graph_filename}")

# === Upload to B2 ===
try:
    print("🔐 Authorizing with B2...")
    info = InMemoryAccountInfo()
    b2_api = B2Api(info)
    b2_api.authorize_account("production", B2_KEY_ID, B2_APPLICATION_KEY)
    bucket = b2_api.get_bucket_by_name(B2_BUCKET_NAME)

    b2_filename = f"{student_email.replace('@', '_').replace('.', '_')}_graph.png"
    print(f"📤 Uploading {graph_filename} to B2 as {b2_filename}...")
    bucket.upload_local_file(local_file=graph_filename, file_name=b2_filename)
    print("✅ Upload complete.")

    # === Generate temporary authorized URL ===
    encoded_filename = quote(b2_filename)
    auth_token = bucket.get_download_authorization(
        file_name_prefix=b2_filename,
        valid_duration_in_seconds=3600  # 1 hour
    )
    graph_url = (
        f"https://f000.backblazeb2.com/file/{B2_BUCKET_NAME}/{encoded_filename}"
        f"?Authorization={auth_token.authorization_token}"
    )
    print(f"🌐 Temporary graph URL: {graph_url}")

    # === Send callback ===
    callback_payload = {
        "student_email": student_email,
        "graph_url": graph_url,
        "pitch_difference": round(pitch_difference, 2),
        "timing_difference": round(timing_difference, 2),
    }

    print(f"📡 Sending result to Zapier: {callback_url}")
    print("📦 Payload:", json.dumps(callback_payload, indent=2))
    r = requests.post(callback_url, json=callback_payload)
    print(f"✅ Callback status: {r.status_code}")
    print(f"📬 Response: {r.text}")

except InvalidAuthToken as e:
    print("❌ Auth error:", e)
    exit(1)
except Exception as e:
    print("❌ Error:", e)
    exit(1)
