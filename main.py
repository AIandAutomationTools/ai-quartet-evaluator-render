import os
import json
import requests
import librosa
import matplotlib.pyplot as plt
import boto3
from botocore.client import Config
from fpdf import FPDF
import time

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

# === Parse payload ===
try:
    payload = json.loads(CLIENT_PAYLOAD_RAW)
    callback_url = payload["callback_url"]
    professor_url = payload["professor_url"]
    student_url = payload["student_url"]
    student_email = payload["student_email"]
    deepgram_feedback = payload.get("deepgram_feedback", "No transcript feedback provided.")
except Exception as e:
    print("❌ Error parsing client_payload")
    print(e)
    exit(1)

# === Download audio files ===
def download_file(url, filename):
    print(f"⬇️ Downloading {url}...")
    response = requests.get(url)
    with open(filename, "wb") as f:
        f.write(response.content)
    print(f"✅ Saved to {filename}")

professor_file = "professor.mp3"
student_file = "student.mp3"
output_graph = "output_graph.png"
output_pdf = "student_report.pdf"
b2_filename_graph = student_email.replace("@", "_").replace(".", "_") + "_graph.png"
b2_filename_pdf = student_email.replace("@", "_").replace(".", "_") + "_report.pdf"

download_file(student_url, student_file)
download_file(professor_url, professor_file)

# === Pitch analysis ===
print("🎼 Extracting pitch...")
prof_y, _ = librosa.load(professor_file)
stud_y, _ = librosa.load(student_file)
prof_pitch = librosa.yin(prof_y, fmin=librosa.note_to_hz('C2'), fmax=librosa.note_to_hz('C7'))
stud_pitch = librosa.yin(stud_y, fmin=librosa.note_to_hz('C2'), fmax=librosa.note_to_hz('C7'))

# === Pitch difference ===
pitch_diff = abs(prof_pitch.mean() - stud_pitch.mean())
timing_diff = abs(len(prof_pitch) - len(stud_pitch))

# === Create pitch graph ===
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

# === Create PDF report ===
print("📝 Generating PDF report...")
pdf = FPDF()
pdf.add_page()
pdf.set_font("Arial", "B", 16)
pdf.cell(0, 10, "Student Singing Evaluation Report", ln=True)

pdf.set_font("Arial", "", 12)
pdf.ln(10)
pdf.cell(0, 10, f"Student Email: {student_email}", ln=True)
pdf.cell(0, 10, f"Pitch Difference: {pitch_diff:.2f} Hz", ln=True)
pdf.cell(0, 10, f"Timing Difference: {timing_diff} frames", ln=True)

pdf.ln(10)
pdf.set_font("Arial", "B", 14)
pdf.cell(0, 10, "Transcript Feedback (Deepgram)", ln=True)
pdf.set_font("Arial", "", 12)
pdf.set_fill_color(240, 240, 240)
pdf.multi_cell(0, 10, str(deepgram_feedback), fill=True)

pdf.output(output_pdf)
print(f"✅ PDF report saved: {output_pdf}")

# === Upload to B2 ===
print("🔐 Uploading to B2 via S3 API...")
s3 = boto3.client(
    's3',
    endpoint_url='https://s3.us-east-005.backblazeb2.com',
    aws_access_key_id=B2_KEY_ID,
    aws_secret_access_key=B2_APPLICATION_KEY,
    config=Config(signature_version='s3v4'),
    region_name='us-east-005'
)

s3.upload_file(output_graph, B2_BUCKET_NAME, b2_filename_graph)
s3.upload_file(output_pdf, B2_BUCKET_NAME, b2_filename_pdf)

# === Generate signed URLs ===
print("🔑 Generating signed URLs...")
signed_url_graph = s3.generate_presigned_url(
    'get_object',
    Params={'Bucket': B2_BUCKET_NAME, 'Key': b2_filename_graph},
    ExpiresIn=3600
)

signed_url_pdf = s3.generate_presigned_url(
    'get_object',
    Params={'Bucket': B2_BUCKET_NAME, 'Key': b2_filename_pdf},
    ExpiresIn=3600
)

# === Build Final Payload ===
print("🧩 Building final payload...")
pitch_diff_value = round(pitch_diff, 2)
timing_diff_value = int(timing_diff)
deepgram_text = str(deepgram_feedback or "No feedback available")

payload_to_zapier = {
    "student_email": student_email,
    "graph_url": signed_url_graph,
    "report_url": signed_url_pdf,
    "pitch_difference": pitch_diff_value,
    "timing_difference": timing_diff_value,
    "deepgram_feedback": deepgram_text
}

# === Optional delay to ensure B2 URLs are accessible
print("⏳ Waiting 2 seconds before sending to Zapier...")
time.sleep(2)

# === Send to Zapier webhook ===
print(f"📡 Sending final payload to Zapier: {callback_url}")
try:
    response = requests.post(callback_url, json=payload_to_zapier)
    print(f"✅ Callback status: {response.status_code}")
    print(f"📬 Response: {response.text}")
except Exception as e:
    print(f"❌ Error sending to Zapier: {e}")
    exit(1)


