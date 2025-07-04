import os
import json
import requests
import librosa
import matplotlib.pyplot as plt
from urllib.parse import quote
from b2sdk.v2 import InMemoryAccountInfo, B2Api

# === Load environment variables ===
print("🔄 Loading environment variables...\n")

B2_KEY_ID = os.getenv("B2_KEY_ID")
B2_APPLICATION_KEY = os.getenv("B2_APPLICATION_KEY")
B2_BUCKET_NAME = os.getenv("B2_BUCKET_NAME")
CLIENT_PAYLOAD_RAW = os.getenv("CLIENT_PAYLOAD")

print("🔍 Env debug:")
print(f"✅ B2_KEY_ID: {B2_KEY_ID}")
print(f"✅ B2_BUCKET_NAME: {B2_BUCKET_NAME}")
print(f"✅ B2_APPLICATION_KEY length: {len(B2_APPLICATION_KEY) if B2_APPLICATION_KEY else 'None'}")
print(f"📦 Raw Payload: {CLIENT_PAYLOAD_RAW}")

if not B2_KEY_ID or not B2_APPLICATION_KEY or not B2_BUCKET_NAME or not CLIENT_PAYLOAD_RAW:
    print("❌ Missing required environment variables.")
    exit(1)

# === Parse JSON payload from Zapier ===
try:
    payload = json.loads(CLIENT_PAYLOAD_RAW)
    callback_url = payload["callback_url"]
    student_email = payload["student_email"]
    student_url = payload["student_url"]
    professor_url = payload["professor_url"]
except Exception as e:
    print("❌ Failed to parse client payload:", e)
    exit(1)

# === Filenames ===
student_file = "student.mp3"
professor_file = "professor.mp3"
graph_file = "output_graph.png"
b2_filename = student_email.replace("@", "_").replace(".", "_") + "_graph.png"

# === Download audio files ===
def download_file(url, output_path):
    print(f"⬇️ Downloading {url}...")
    response = requests.get(url)
    if response.status_code != 200:
        raise Exception(f"Failed to download: {url}")
    with open(output_path, "wb") as f:
        f.write(response.content)
    print(f"✅ Saved to {output_path}")

download_file(student_url, student_file)
download_file(professor_url, professor_file)

# === Analyze pitch ===
print("🎼 Extracting pitch...")
prof_y, _ = librosa.load(professor_file)
stud_y, _ = librosa.load(student_file)
prof_pitch = librosa.yin(prof_y, fmin=librosa.note_to_hz('C2'), fmax=librosa.note_to_hz('C7'))
stud_pitch = librosa.yin(stud_y, fmin=librosa.note_to_hz('C2'), fmax=librosa.note_to_hz('C7'))

# === Create pitch comparison graph ===
plt.figure(figsize=(10, 4))
plt.plot(prof_pitch, label="Professor", alpha=0.7)
plt.plot(stud_pitch, label="Student", alpha=0.7)
plt.legend()
plt.title("Pitch Comparison")
plt.xlabel("Time Frame")
plt.ylabel("Frequency (Hz)")
plt.tight_layout()
plt.savefig(graph_file)
print(f"✅ Graph saved: {graph_file}")

# === Upload to B2 ===
print("🔐 Authorizing with B2...")
info = InMemoryAccountInfo()
b2_api = B2Api(info)
b2_api.authorize_account("production", B2_KEY_ID, B2_APPLICATION_KEY)
bucket = b2_api.get_bucket_by_name(B2_BUCKET_NAME)

print(f"📤 Uploading {graph_file} to B2 as {b2_filename}...")
bucket.upload_local_file(local_file=graph_file, file_name=b2_filename)
print("✅ Upload complete.")

# === Generate temporary signed URL (valid 1 hour) ===
print("🔑 Generating temporary signed URL...")
download_auth = b2_api.get_download_authorization(
    bucket_id=bucket.id_,
    file_name_prefix=b2_filename,
    valid_duration_in_seconds=3600  # 1 hour
)

encoded_filename = quote(b2_filename)
signed_url = (
    f"https://s3.us-east-005.backblazeb2.com/{B2_BUCKET_NAME}/{encoded_filename}"
    f"?Authorization={download_auth.authorization_token}"
)

print(f"🌐 Temporary Graph URL: {signed_url}")

# === Send callback ===
payload_to_zapier = {
    "student_email": student_email,
    "graph_url": signed_url,
    "pitch_difference": "2.3 Hz",     # Placeholder value
    "timing_difference": "0.4 sec",   # Placeholder value
}

print(f"📬 Sending result to Zapier webhook: {callback_url}")
response = requests.post(callback_url, json=payload_to_zapier)
print(f"✅ Webhook sent! Status: {response.status_code}")
print("📨 Payload sent:", json.dumps(payload_to_zapier, indent=2))
