import os
import json
import requests
import librosa
import matplotlib.pyplot as plt
import boto3
from botocore.client import Config

from urllib.parse import urlparse

# === Load environment variables ===
print("\U0001f504 Loading environment variables...")

B2_KEY_ID = os.getenv("B2_KEY_ID")
B2_APPLICATION_KEY = os.getenv("B2_APPLICATION_KEY")
B2_BUCKET_NAME = os.getenv("B2_BUCKET_NAME")
CLIENT_PAYLOAD_RAW = os.getenv("CLIENT_PAYLOAD")

print("\n\U0001f50d Env debug:")
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

professor_file = "professor.mp3"
student_file = "student.mp3"
output_graph = "output_graph.png"

# === Download audio files ===
def download_file(url, filename):
    print(f"⬇️ Downloading {url}...")
    response = requests.get(url)
    with open(filename, "wb") as f:
        f.write(response.content)
    print(f"✅ Saved to {filename}")

download_file(student_url, student_file)
download_file(professor_url, professor_file)

# === Extract pitch and generate graph ===
print("🎼 Extracting pitch...")
prof_y, _ = librosa.load(professor_file)
stud_y, _ = librosa.load(student_file)
prof_pitch = librosa.yin(prof_y, fmin=librosa.note_to_hz('C2'), fmax=librosa.note_to_hz('C7'))
stud_pitch = librosa.yin(stud_y, fmin=librosa.note_to_hz('C2'), fmax=librosa.note_to_hz('C7'))

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

# === Upload to B2 using boto3 ===
print("🔐 Authorizing with B2 via S3 API...")
s3 = boto3.client(
    's3',
    endpoint_url='https://s3.us-east-005.backblazeb2.com',
    aws_access_key_id=B2_KEY_ID,
    aws_secret_access_key=B2_APPLICATION_KEY,
    config=Config(signature_version='s3v4'),
    region_name='us-east-005'
)

b2_filename = student_email.replace("@", "_").replace(".", "_") + "_graph.png"

print(f"📄 Uploading {output_graph} to B2 as {b2_filename}...")
s3.upload_file(output_graph, B2_BUCKET_NAME, b2_filename)
print("✅ Upload complete.")

# === Generate signed URL ===
print("🔑 Generating temporary signed URL...")
signed_url = s3.generate_presigned_url(
    'get_object',
    Params={'Bucket': B2_BUCKET_NAME, 'Key': b2_filename},
    ExpiresIn=3600  # 1 hour
)

print(f"🌐 Temporary Graph URL: {signed_url}")

# === Send callback ===
payload_to_zapier = {
    "student_email": student_email,
    "student_url": student_url,
    "professor_url": professor_url,
    "graph_url": signed_url
}

print(f"📡 Sending to callback URL: {callback_url}")
response = requests.post(callback_url, json=payload_to_zapier)
print(f"✅ Callback status: {response.status_code}")
print(f"📬 Response: {response.text}")

