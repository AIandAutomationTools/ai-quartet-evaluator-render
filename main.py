import os
import json
import requests
import librosa
import matplotlib.pyplot as plt
from b2sdk.v2 import InMemoryAccountInfo, B2Api
from b2sdk.v2.exception import InvalidAuthToken
from datetime import timedelta

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

# === Download audio files ===
def download_file(url, dest_filename):
    print(f"⬇️ Downloading {url}...")
    r = requests.get(url)
    if r.status_code != 200:
        raise Exception(f"❌ Failed to download {url} → {r.status_code}")
    with open(dest_filename, "wb") as f:
        f.write(r.content)
    print(f"✅ Saved to {dest_filename}")

download_file(student_url, "student.mp3")
download_file(professor_url, "professor.mp3")

# === Load audio and compute pitch ===
print("🎼 Extracting pitch...")
prof_y, _ = librosa.load("professor.mp3")
stud_y, _ = librosa.load("student.mp3")

prof_pitch = librosa.yin(prof_y, fmin=librosa.note_to_hz('C2'), fmax=librosa.note_to_hz('C7'))
stud_pitch = librosa.yin(stud_y, fmin=librosa.note_to_hz('C2'), fmax=librosa.note_to_hz('C7'))

# === Calculate average pitch difference (in Hz) ===
pitch_diff = abs(prof_pitch.mean() - stud_pitch.mean())
timing_diff = abs(len(prof_pitch) - len(stud_pitch)) / 100  # crude timing comparison

# === Create graph ===
output_graph = "output_graph.png"
plt.figure(figsize=(10, 4))
plt.plot(prof_pitch, label="Professor", alpha=0.7)
plt.plot(stud_pitch, label="Student", alpha=0.7)
plt.legend()
plt.title("Pitch Comparison")
plt.xlabel("Time Frame")
plt.ylabel("Frequency (Hz)")
plt.tight_layout()
plt.savefig(output_graph)
print(f"✅ Graph saved: {output_graph}")

# === Upload to B2 and generate temp URL ===
try:
    print("🔐 Authorizing with B2...")
    info = InMemoryAccountInfo()
    b2_api = B2Api(info)
    b2_api.authorize_account("production", B2_KEY_ID, B2_APPLICATION_KEY)
    bucket = b2_api.get_bucket_by_name(B2_BUCKET_NAME)

    b2_filename = f"{student_email.replace('@', '_')}_graph.png"
    print(f"📤 Uploading {output_graph} to B2 as {b2_filename}...")
    uploaded_file = bucket.upload_local_file(
        local_file=output_graph,
        file_name=b2_filename,
    )
    print("✅ Upload complete.")

    # === Generate temporary URL (valid 1 hour) ===
    temp_url = bucket.get_download_url_by_name(
        b2_filename,
        authorization=b2_api.get_download_authorization(
            file_name=b2_filename,
            valid_duration_seconds=3600
        )
    )
    print(f"🌐 Temporary URL: {temp_url}")

    # === Send callback ===
    payload_to_zapier = {
        "student_email": student_email,
        "graph_url": temp_url,
        "pitch_difference": round(pitch_diff, 2),
        "timing_difference": round(timing_diff, 2)
    }

    print(f"📡 Sending result to Zapier: {callback_url}")
    print("📦 Payload:", json.dumps(payload_to_zapier, indent=2))
    response = requests.post(callback_url, json=payload_to_zapier)
    print(f"✅ Callback status: {response.status_code}")
    print(f"📬 Response: {response.text}")

except InvalidAuthToken as e:
    print("❌ Auth error:", e)
    exit(1)
except Exception as e:
    print("❌ Error:", e)
    exit(1)

