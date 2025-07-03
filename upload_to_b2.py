import os
import json
import requests
from b2sdk.v2 import InMemoryAccountInfo, B2Api
from b2sdk.v2.exception import InvalidAuthToken

# === Load environment variables ===
B2_KEY_ID = os.getenv("B2_KEY_ID")
B2_APP_KEY = os.getenv("B2_APP_KEY")  # Was incorrectly named in earlier version
B2_BUCKET_NAME = os.getenv("B2_BUCKET_NAME")
CLIENT_PAYLOAD_RAW = os.getenv("CLIENT_PAYLOAD")

if not all([B2_KEY_ID, B2_APP_KEY, B2_BUCKET_NAME]):
    raise EnvironmentError("❌ One or more required B2 environment variables are missing!")

if CLIENT_PAYLOAD_RAW is None:
    raise ValueError("CLIENT_PAYLOAD is missing.")

# === Parse client payload ===
payload = json.loads(CLIENT_PAYLOAD_RAW)
callback_url = payload["callback_url"]
student_url = payload["student_url"]
professor_url = payload["professor_url"]
student_email = payload["student_email"]

print("✅ Loaded client payload.")
print(f"👤 Student: {student_email}")
print(f"🎧 Student URL: {student_url}")
print(f"🎧 Professor URL: {professor_url}")

# === Download files ===
student_filename = "student.mp3"
professor_filename = "professor.mp3"

def download_file(url, dest_filename):
    print(f"⬇️ Downloading {url}...")
    r = requests.get(url)
    if r.status_code != 200:
        raise Exception(f"Failed to download {url} → {r.status_code}")
    with open(dest_filename, "wb") as f:
        f.write(r.content)
    print(f"✅ Saved to {dest_filename}")

download_file(student_url, student_filename)
download_file(professor_url, professor_filename)

# === Create dummy graph (simulate audio analysis) ===
graph_filename = "output_graph.png"
with open(graph_filename, "wb") as f:
    f.write(b"FAKE IMAGE DATA FOR GRAPH PLACEHOLDER")
print(f"🖼️ Created placeholder graph at {graph_filename}")

# === Upload to Backblaze B2 ===
print("🔐 Authorizing with Backblaze B2...")
info = InMemoryAccountInfo()
b2_api = B2Api(info)

print(f"🔎 B2_KEY_ID: {B2_KEY_ID}")
print(f"🔎 B2_APP_KEY starts with: {B2_APP_KEY[:6]}... (length: {len(B2_APP_KEY)})")
print(f"🔎 B2_BUCKET_NAME: {B2_BUCKET_NAME}")

b2_api.authorize_account("production", B2_KEY_ID, B2_APP_KEY)
bucket = b2_api.get_bucket_by_name(B2_BUCKET_NAME)
if not bucket:
    raise Exception(f"Bucket '{B2_BUCKET_NAME}' not found.")

b2_filename = f"{student_email}_graph.png"
print(f"📤 Uploading {graph_filename} to B2 as {b2_filename}...")
b2_file = bucket.upload_local_file(
    local_file=graph_filename,
    file_name=b2_filename,
)
download_url = f"https://f000.backblazeb2.com/file/{bucket.name}/{b2_filename}"
print(f"✅ Uploaded to: {download_url}")

# === Callback to Zapier ===
print("📬 Sending result to callback URL...")
callback_payload = {
    "student_email": student_email,
    "public_download_url": download_url,
    "professor_url": professor_url,
    "student_url": student_url
}

print(f"📤 Sending to callback URL: {callback_url}")
print("📦 Payload:", json.dumps(callback_payload, indent=2))

r = requests.post(callback_url, json=callback_payload)
if r.status_code != 200:
    raise Exception(f"Callback failed → {r.status_code}:\n{r.text}")
print("✅ Callback sent successfully.")

