import os
import json
import requests
import librosa
import numpy as np
import matplotlib.pyplot as plt
import boto3
from botocore.client import Config
from librosa.sequence import dtw

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
    print("❌ ERROR: Missing environment variables")
    exit(1)

# === Parse Payload ===
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

avg_pitch_diff = float(np.mean(np.abs(prof_pitch[:len(stud_pitch)] - stud_pitch))) if len(stud_pitch) > 0 else None
print(f"🎯 Avg pitch difference: {avg_pitch_diff:.2f} Hz")

# === Create graph ===
plt.figure(figsize=(10, 4))
plt.plot(prof_pitch, label="Professor", alpha=0.7)
plt.plot(stud_pitch, label="Student", alpha=0.7)
plt.legend()
plt.title("Pitch Comparison")
plt.xlabel("Frame")
plt.ylabel("Frequency (Hz)")
plt.tight_layout()
graph_file = "output_graph.png"
plt.savefig(graph_file)
print(f"✅ Graph saved: {graph_file}")

# === Timing comparison ===
print("🕒 Comparing timing...")
prof_onsets = librosa.onset.onset_detect(y=prof_y, sr=sr, units='time')
stud_onsets = librosa.onset.onset_detect(y=stud_y, sr=sr, units='time')

prof_onset_vec = np.expand_dims(prof_onsets, axis=0)
stud_onset_vec = np.expand_dims(stud_onsets, axis=0)

D, wp = dtw(X=prof_onset_vec, Y=stud_onset_vec, metric='euclidean')
timing_diffs = [abs(prof_onsets[i] - stud_onsets[j]) for i, j in wp if i < len(prof_onsets) and j < len(stud_onsets)]
avg_timing_diff = round(np.mean(timing_diffs), 3) if timing_diffs else None
print(f"⏱️ Avg timing difference: {avg_timing_diff} seconds")

# === Score calculation ===
pitch_penalty = min(avg_pitch_diff or 0, 300) / 300
timing_penalty = min(avg_timing_diff or 0, 1.0) / 1.0
performance_score = round((1.0 - (0.6 * pitch_penalty + 0.4 * timing_penalty)) * 100)
print(f"🏆 Performance Score: {performance_score}/100")

# === Upload to B2 ===
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
print(f"📤 Uploading {graph_file} to B2 as {b2_filename}...")
s3.upload_file(graph_file, B2_BUCKET_NAME, b2_filename)
print("✅ Upload complete.")

# === Generate signed URL ===
print("🔑 Generating temporary signed URL...")
signed_url = s3.generate_presigned_url(
    'get_object',
    Params={'Bucket': B2_BUCKET_NAME, 'Key': b2_filename},
    ExpiresIn=3600  # 1 hour
)
print(f"🌐 Temporary Graph URL: {signed_url}")

# === Send result to Zapier webhook ===
callback_payload = {
    "student_email": student_email,
    "student_url": student_url,
    "professor_url": professor_url,
    "graph_url": signed_url,
    "pitch_diff": round(avg_pitch_diff, 2),
    "timing_diff": avg_timing_diff,
    "performance_score": performance_score
}

print(f"📡 Sending callback to {callback_url}")
r = requests.post(callback_url, json=callback_payload)
if r.status_code != 200:
    print(f"❌ Callback failed: {r.status_code} - {r.text}")
    exit(1)

print("✅ Callback sent successfully.")

