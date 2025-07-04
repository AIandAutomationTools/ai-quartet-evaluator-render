import os
import json
import requests
import librosa
import matplotlib.pyplot as plt
import numpy as np
import boto3
from botocore.client import Config
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

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
prof_y, sr = librosa.load(professor_file)
stud_y, _ = librosa.load(student_file)
prof_pitch = librosa.yin(prof_y, fmin=librosa.note_to_hz('C2'), fmax=librosa.note_to_hz('C7'))
stud_pitch = librosa.yin(stud_y, fmin=librosa.note_to_hz('C2'), fmax=librosa.note_to_hz('C7'))

# Trim to same length
min_len = min(len(prof_pitch), len(stud_pitch))
prof_pitch = prof_pitch[:min_len]
stud_pitch = stud_pitch[:min_len]

# Calculate differences
pitch_diffs = np.abs(prof_pitch - stud_pitch)
avg_pitch_diff = np.mean(pitch_diffs)
timing_diff = abs(len(prof_y) - len(stud_y)) / sr
performance_score = max(0, 100 - (avg_pitch_diff * 2 + timing_diff * 10))
performance_score = round(performance_score, 2)

# Generate feedback
if performance_score > 85:
    feedback = "Excellent performance! Your pitch and timing are well aligned with the reference recording."
elif performance_score > 70:
    feedback = "Good job! Minor discrepancies in pitch or timing, but overall strong."
elif performance_score > 50:
    feedback = "Decent attempt. There are some noticeable differences in pitch or timing. Review the graph to improve."
else:
    feedback = "Keep practicing! Your performance has room for improvement in pitch and/or timing."
print(f"💬 Feedback: {feedback}")

# Generate pitch comparison graph
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
signed_url = s3.generate_presigned_url(
    'get_object',
    Params={'Bucket': B2_BUCKET_NAME, 'Key': b2_filename},
    ExpiresIn=3600
)
print(f"🌐 Graph URL: {signed_url}")

# === Generate PDF report ===
pdf_filename = student_email.replace("@", "_").replace(".", "_") + "_report.pdf"
print("📄 Generating PDF report...")
c = canvas.Canvas(pdf_filename, pagesize=letter)
c.setFont("Helvetica-Bold", 16)
c.drawString(50, 750, "Quartet Singing Evaluation Report")
c.setFont("Helvetica", 12)
c.drawString(50, 720, f"Student: {student_email}")
c.drawString(50, 700, f"Performance Score: {performance_score}/100")
c.drawString(50, 680, f"Pitch Difference: {round(avg_pitch_diff, 2)} Hz")
c.drawString(50, 660, f"Timing Difference: {round(timing_diff, 2)} seconds")
text = c.beginText(50, 620)
text.setFont("Helvetica-Oblique", 11)
text.textLines("Feedback:\n" + feedback)
c.drawText(text)
c.drawImage(output_graph, 50, 380, width=500, preserveAspectRatio=True, mask='auto')
c.showPage()
c.save()
print(f"✅ PDF generated: {pdf_filename}")

pdf_key = pdf_filename
print(f"📤 Uploading PDF report to B2 as {pdf_key}...")
s3.upload_file(pdf_filename, B2_BUCKET_NAME, pdf_key)
pdf_signed_url = s3.generate_presigned_url(
    'get_object',
    Params={'Bucket': B2_BUCKET_NAME, 'Key': pdf_key},
    ExpiresIn=3600
)
print(f"🌐 PDF Report URL: {pdf_signed_url}")

# === Callback payload ===
callback_payload = {
    "student_email": student_email,
    "student_url": student_url,
    "professor_url": professor_url,
    "graph_url": signed_url,
    "pdf_report_url": pdf_signed_url,
    "pitch_diff": round(avg_pitch_diff, 2),
    "timing_diff": round(timing_diff, 2),
    "performance_score": performance_score,
    "feedback": feedback
}

print(f"📡 Sending to callback URL: {callback_url}")
response = requests.post(callback_url, json=callback_payload)
print(f"✅ Callback status: {response.status_code}")
print(f"📬 Response: {response.text}")

