import os
import json
import librosa
import matplotlib.pyplot as plt
import requests
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

# === Filenames ===
professor_file = "professor.mp3"
student_file = "student.mp3"
graph_filename = "output_graph.png"

# === Download files ===
def download_file(url, dest):
    print(f"⬇️ Downloading {url}...")
    r = requests.get(url)
    if r.status_code != 200:
        print(f"❌ Failed to download {url} → {r.status_code}")
        exit(1)
    with open(dest, "wb") as f:
        f.write(r.content)
    print(f"✅ Saved to {dest}")

download_file(student_url, student_file)
download_file(professor_url, professor_file)

# === Pitch Analysis ===
print("🎼 Extracting pitch...")
prof_y, _ = librosa.load(professor_file)
stud_y, _ = librosa.load(student_file)

prof_pitch = librosa.yin(prof_y, fmin=librosa.note_to_hz('C2'), fmax=librosa.note_to_hz('C7'))
stud_pitch = librosa.yin(stud_y, fmin=librosa.note_to_hz('C2'), fmax=librosa.note_to_hz('C7'))

# Calculate basic pitch and timing difference (simplified)
pitch_diff = abs(prof_pitch.mean() - stud_pitch.mean())
timing_diff = abs(len(prof_pitch) - len(stud_pitch)) / 100.0  # arbitrary unit

# === Create graph ===
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

# === Upload to B2 ===
try:
    print("🔐 Authorizing with B2...")
    info = InMemoryAccountInfo()
    b2_api = B2Api(info)
    b2_api.authorize_account("production", B2_KEY_ID, B2_APPLICATION_KEY)
    bucket = b2_api.get_bucket_by_name(B2_BUCKET_NAME)

    b2_filename = student_email.replace("@", "_").replace(".", "_") + "_graph.png"
    print(f"📤 Uploading {graph_filename} to B2 as {b2_filename}...")
    b2_file = bucket.upload_local_file(local_file=graph_filename, file_name=b2_filename)
    print("✅ Upload complete.")

    # Generate temporary download URL (signed URL)
    from b2sdk.v2 import DownloadAuthorization
    auth_token = bucket.get_download_authorization(file_name_prefix=b2_filename, valid_duration_in_seconds=3600)
    encoded_filename = quote(b2_filename)
    download_url = f"https://s3.us-east-005.backblazeb2.com/{B2_BUCKET_NAME}/{encoded_filename}?Authorization={auth_token.authorization_token}"
    print(f"🌐 Temporary Download URL: {download_url}")

    # === Send callback ===
    payload_to_zapier = {
        "student_email": student_email,
        "student_url": student_url,
        "professor_url": professor_url,
        "graph_url": download_url,
        "pitch_difference": round(float(pitch_diff), 2),
        "timing_difference": round(float(timing_diff), 2)
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

