import os
import json
import requests
import librosa
import matplotlib.pyplot as plt
from urllib.parse import quote
from b2sdk.v2 import InMemoryAccountInfo, B2Api
from b2sdk.v2.exception import InvalidAuthToken

# === Load environment variables ===
print("🔄 Loading environment variables...\n")

B2_KEY_ID = os.getenv("B2_KEY_ID")
B2_APPLICATION_KEY = os.getenv("B2_APPLICATION_KEY")
B2_BUCKET_NAME = os.getenv("B2_BUCKET_NAME")
CLIENT_PAYLOAD_RAW = os.getenv("CLIENT_PAYLOAD")

print(f"🔍 Env debug:")
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
    print("❌ Error parsing client_payload:", e)
    exit(1)

# === Filenames ===
professor_file = "professor.mp3"
student_file = "student.mp3"
output_graph = "output_graph.png"
b2_filename = f"{student_email.replace('@', '_').replace('.', '_')}_graph.png"

# === Download helper ===
def download_file(url, dest):
    print(f"⬇️ Downloading {url}...")
    r = requests.get(url)
    if r.status_code != 200:
        raise Exception(f"Failed to download {url} → {r.status_code}")
    with open(dest, "wb") as f:
        f.write(r.content)
    print(f"✅ Saved to {dest}")

try:
    # === Download student and professor audio ===
    download_file(student_url, student_file)
    download_file(professor_url, professor_file)

    # === Extract pitch using librosa ===
    print("🎼 Extracting pitch...")
    prof_y, _ = librosa.load(professor_file)
    stud_y, _ = librosa.load(student_file)

    prof_pitch = librosa.yin(prof_y, fmin=librosa.note_to_hz('C2'), fmax=librosa.note_to_hz('C7'))
    stud_pitch = librosa.yin(stud_y, fmin=librosa.note_to_hz('C2'), fmax=librosa.note_to_hz('C7'))

    # === Calculate basic differences ===
    pitch_diff = float(abs(prof_pitch.mean() - stud_pitch.mean()))
    timing_diff = float(abs(len(prof_pitch) - len(stud_pitch)))

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
    print("🔐 Authorizing with B2...")
    info = InMemoryAccountInfo()
    b2_api = B2Api(info)
    b2_api.authorize_account("production", B2_KEY_ID, B2_APPLICATION_KEY)

    bucket = b2_api.get_bucket_by_name(B2_BUCKET_NAME)
    print(f"📤 Uploading {output_graph} to B2 as {b2_filename}...")
    b2_file = bucket.upload_local_file(local_file=output_graph, file_name=b2_filename)
    print("✅ Upload complete.")

    # === Generate temporary authorized URL ===
    encoded_filename = quote(b2_filename)
    download_auth_token = b2_api.get_download_authorization(bucket_id=bucket.id_, file_name_prefix=b2_filename, valid_duration_in_seconds=3600)
    graph_url = (
        f"https://f000.backblazeb2.com/file/{B2_BUCKET_NAME}/{encoded_filename}"
        f"?Authorization={download_auth_token.authorization_token}"
    )
    print(f"🌐 Temporary download URL: {graph_url}")

    # === Send results to Zapier ===
    payload_to_zapier = {
        "student_email": student_email,
        "student_url": student_url,
        "professor_url": professor_url,
        "graph_url": graph_url,
        "pitch_difference": pitch_diff,
        "timing_difference": timing_diff
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

