import os
import json
import librosa
import matplotlib.pyplot as plt
import requests
from b2sdk.v2 import InMemoryAccountInfo, B2Api
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

# === Download files ===
def download_file(url, filename):
    print(f"⬇️ Downloading {url}...")
    r = requests.get(url)
    if r.status_code != 200:
        raise Exception(f"Failed to download {url} → {r.status_code}")
    with open(filename, "wb") as f:
        f.write(r.content)
    print(f"✅ Saved to {filename}")

download_file(student_url, "student.mp3")
download_file(professor_url, "professor.mp3")

# === Load audio and compute pitch ===
print("🎼 Extracting pitch...")
prof_y, _ = librosa.load("professor.mp3")
stud_y, _ = librosa.load("student.mp3")

prof_pitch = librosa.yin(prof_y, fmin=librosa.note_to_hz('C2'), fmax=librosa.note_to_hz('C7'))
stud_pitch = librosa.yin(stud_y, fmin=librosa.note_to_hz('C2'), fmax=librosa.note_to_hz('C7'))

# === Calculate simple average differences (just for demo)
pitch_diff = abs(prof_pitch.mean() - stud_pitch.mean())
timing_diff = abs(len(prof_pitch) - len(stud_pitch))

# === Create pitch comparison graph
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

# === Upload to Backblaze B2
print("🔐 Authorizing with B2...")
info = InMemoryAccountInfo()
b2_api = B2Api(info)
b2_api.authorize_account("production", B2_KEY_ID, B2_APPLICATION_KEY)
bucket = b2_api.get_bucket_by_name(B2_BUCKET_NAME)

# Upload file
b2_filename = student_email.replace("@", "_").replace(".", "_") + "_graph.png"
print(f"📤 Uploading {graph_filename} to B2 as {b2_filename}...")
bucket.upload_local_file(
    local_file=graph_filename,
    file_name=b2_filename
)
print("✅ Upload complete.")

# Generate signed URL (temporary access)
endpoint = "https://s3.us-east-005.backblazeb2.com"
auth_token = b2_api.account_info.get_account_auth_token()
encoded_filename = quote(b2_filename)
signed_url = f"{endpoint}/{B2_BUCKET_NAME}/{encoded_filename}?Authorization={auth_token}"
print(f"🌐 Temporary Graph URL: {signed_url}")

# === Send result to Zapier
callback_payload = {
    "student_email": student_email,
    "graph_url": signed_url,
    "pitch_difference": round(pitch_diff, 2),
    "timing_difference": timing_diff,
    "student_url": student_url,
    "professor_url": professor_url
}

print(f"📡 Sending result to Zapier: {callback_url}")
print("📦 Payload:", json.dumps(callback_payload, indent=2))
response = requests.post(callback_url, json=callback_payload)
print(f"✅ Callback status: {response.status_code}")
print(f"📬 Response: {response.text}")

