import os
import json
import librosa
import matplotlib.pyplot as plt
import requests
from b2sdk.v2 import InMemoryAccountInfo, B2Api
from b2sdk.v2.exception import InvalidAuthToken

# === Load environment variables ===
print("🔄 Loading environment variables...")

B2_KEY_ID = os.getenv("B2_KEY_ID")
B2_APPLICATION_KEY = os.getenv("B2_APP_KEY")
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

# === Assume professor.mp3 and student.mp3 already exist ===
professor_file = "professor.mp3"
student_file = "student.mp3"
output_graph = "output_graph.png"

# === Verify files exist ===
for f in [professor_file, student_file]:
    if not os.path.exists(f):
        print(f"❌ Missing file: {f}")
        exit(1)

# === Load audio and compute pitch ===
print("🎼 Extracting pitch...")
prof_y, _ = librosa.load(professor_file)
stud_y, _ = librosa.load(student_file)

prof_pitch = librosa.yin(prof_y, fmin=librosa.note_to_hz('C2'), fmax=librosa.note_to_hz('C7'))
stud_pitch = librosa.yin(stud_y, fmin=librosa.note_to_hz('C2'), fmax=librosa.note_to_hz('C7'))

# === Create graph ===
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

# === Upload to B2 ===
try:
    print("🔐 Authorizing with B2...")
    info = InMemoryAccountInfo()
    b2_api = B2Api(info)
    b2_api.authorize_account("production", B2_KEY_ID, B2_APPLICATION_KEY)
    bucket = b2_api.get_bucket_by_name(B2_BUCKET_NAME)

    print(f"📤 Uploading {output_graph}...")
    bucket.upload_local_file(
        local_file=output_graph,
        file_name=output_graph,
    )
    print("✅ Upload complete.")

    # === Build Public Download URL ===
    download_url = f"https://f000.backblazeb2.com/file/{B2_BUCKET_NAME}/{output_graph}"
    print(f"🌐 Download URL: {download_url}")

    # === Send callback to Zapier ===
    payload_to_zapier = {
        "student_email": student_email,
        "student_url": student_url,
        "professor_url": professor_url,
        "graph_url": download_url
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
