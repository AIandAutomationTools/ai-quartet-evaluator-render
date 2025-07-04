import os
import json
import requests
import librosa
import matplotlib.pyplot as plt
import datetime
import hashlib
import hmac
from urllib.parse import quote_plus

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

# === Parse JSON payload ===
try:
    payload = json.loads(CLIENT_PAYLOAD_RAW)
    callback_url = payload["callback_url"]
    student_email = payload["student_email"]
    student_url = payload["student_url"]
    professor_url = payload["professor_url"]
except Exception as e:
    print("❌ Failed to parse client payload:", e)
    exit(1)

# === Prepare file names ===
student_file = "student.mp3"
professor_file = "professor.mp3"
graph_file = "output_graph.png"
b2_filename = student_email.replace("@", "_").replace(".", "_") + "_graph.png"

# === Download files ===
def download_file(url, output_path):
    print(f"⬇️ Downloading {url}...")
    r = requests.get(url)
    if r.status_code != 200:
        raise Exception(f"❌ Failed to download file: {url}")
    with open(output_path, "wb") as f:
        f.write(r.content)
    print(f"✅ Saved to {output_path}")

download_file(student_url, student_file)
download_file(professor_url, professor_file)

# === Extract pitch ===
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

# === Create S3-style signed URL manually ===
def generate_s3_signed_url(access_key, secret_key, region, bucket, object_key, expires_in=3600):
    method = "GET"
    service = "s3"
    host = f"s3.{region}.backblazeb2.com"
    endpoint = f"https://{host}/{bucket}/{quote_plus(object_key)}"
    now = datetime.datetime.utcnow()
    amz_date = now.strftime("%Y%m%dT%H%M%SZ")
    datestamp = now.strftime("%Y%m%d")

    credential_scope = f"{datestamp}/{region}/{service}/aws4_request"
    signed_headers = "host"
    canonical_headers = f"host:{host}\n"
    payload_hash = hashlib.sha256(b"").hexdigest()

    canonical_request = "\n".join([
        method,
        f"/{bucket}/{object_key}",
        "",
        canonical_headers,
        signed_headers,
        payload_hash
    ])

    string_to_sign = "\n".join([
        "AWS4-HMAC-SHA256",
        amz_date,
        credential_scope,
        hashlib.sha256(canonical_request.encode()).hexdigest()
    ])

    def sign(key, msg):
        return hmac.new(key, msg.encode('utf-8'), hashlib.sha256).digest()

    date_key = sign(("AWS4" + secret_key).encode('utf-8'), datestamp)
    date_region_key = sign(date_key, region)
    date_region_service_key = sign(date_region_key, service)
    signing_key = sign(date_region_service_key, "aws4_request")

    signature = hmac.new(signing_key, string_to_sign.encode('utf-8'), hashlib.sha256).hexdigest()

    params = {
        "X-Amz-Algorithm": "AWS4-HMAC-SHA256",
        "X-Amz-Credential": f"{access_key}/{credential_scope}",
        "X-Amz-Date": amz_date,
        "X-Amz-Expires": str(expires_in),
        "X-Amz-SignedHeaders": signed_headers,
        "X-Amz-Signature": signature
    }

    param_str = "&".join(f"{k}={quote_plus(v)}" for k, v in params.items())
    return f"{endpoint}?{param_str}"

print("🔑 Generating signed URL...")
signed_url = generate_s3_signed_url(
    access_key=B2_KEY_ID,
    secret_key=B2_APPLICATION_KEY,
    region="us-east-005",
    bucket=B2_BUCKET_NAME,
    object_key=b2_filename,
    expires_in=3600
)

print(f"🌐 Signed Graph URL: {signed_url}")

# === Send webhook ===
payload_to_zapier = {
    "student_email": student_email,
    "graph_url": signed_url,
    "pitch_difference": "2.3 Hz",     # Placeholder
    "timing_difference": "0.4 sec"    # Placeholder
}

print(f"📬 Sending result to Zapier: {callback_url}")
response = requests.post(callback_url, json=payload_to_zapier)
print(f"✅ Webhook status: {response.status_code}")
print("📨 Sent Payload:", json.dumps(payload_to_zapier, indent=2))

