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
B2_APPLICATION_KEY = os.getenv("B2_APPLICATION_KEY")
B2_BUCKET_NAME = os.getenv("B2_BUCKET_NAME")
CLIENT_PAYLOAD_RAW = os.getenv("CLIENT_PAYLOAD")

if not all([B2_KEY_ID, B2_APPLICATION_KEY, B2_BUCKET_NAME, CLIENT_PAYLOAD_RAW]):
    print("❌ Missing environment variables.")
    exit(1)

# === Parse client payload ===
try:
    payload = json.loads(CLIENT_PAYLOAD_RAW)
    callback_url = payload["callback_url"]
    professor_url = payload["professor_url"]
    student_url = payload["student_url"]
    student_email = payload["student_email"]
except Exception as e:
    print("❌ Error parsing client payload:", e)
    exit(1)

professor_file = "professor.mp3"
student_file = "student.mp3"
output_graph = "output_graph.png"

# === Verify audio files exist ===
for f in [professor_file, student_file]:
    if not os.path.exists(f):
        print(f"❌ Missing file: {f}")
        exit(1)

# === Analyze audio files ===
print("🎼 Performing pitch analysis...")
prof_y, sr1 = librosa.load(professor_file)
stud_y, sr2 = librosa.load(student_file)

prof_pitch = librosa.yin(prof_y, fmin=librosa.note_to_hz('C2'), fmax=librosa.note_to_hz('C7'))
stud_pitch = librosa.yin(stud_y, fmin=librosa.note_to_hz('C2'), fmax=librosa.note_to_hz('C7'))

# === Calculate average pitch difference ===
avg_pitch_diff = abs(prof_pitch.mean() - stud_pitch.mean())

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

    b2_filename = f"{student_email.replace('@', '_at_')}_graph.png"
    print(f"📤 Uploading file as: {b2_filename}")
    uploaded_file = bucket.upload_local_file(
        local_file=output_graph,
        file_name=b2_filename,
    )

    # === Create temporary download URL (valid for 1 hour = 3600s)
    print("🔗 Creating temporary download URL...")
    temp_url = b2_api.get_download_url_with_auth(
        bucket_id=bucket.id_,
        file_name=b2_filename,
        valid_duration_seconds=3600  # 1 hour
    )

    print(f"🌐 Temporary URL: {temp_url}")

    # === Send data to Zapier
    result = {
        "student_email": student_email,
        "graph_url": temp_url,
        "pitch_difference": round(avg_pitch_diff, 2),
        "professor_url": professor_url,
        "student_url": student_url
    }

    print(f"📬 Sending to Zapier: {callback_url}")
    response = requests.post(callback_url, json=result)
    print(f"✅ Webhook status: {response.status_code}")
    print(f"📦 Webhook payload: {json.dumps(result, indent=2)}")

except InvalidAuthToken as e:
    print("❌ Auth error:", e)
    exit(1)
except Exception as e:
    print("❌ Unexpected error:", e)
    exit(1)
