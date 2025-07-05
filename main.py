# ... [same imports and setup code] ...

# === Download files ===
download_file(student_url, student_file)
download_file(professor_url, professor_file)

# === Pitch analysis ===
print("🎼 Extracting pitch...")
try:
    prof_y, _ = librosa.load(professor_file)
    stud_y, _ = librosa.load(student_file)
except Exception as e:
    print(f"❌ Error loading audio: {e}")
    exit(1)

prof_pitch = librosa.yin(prof_y, fmin=librosa.note_to_hz('C2'), fmax=librosa.note_to_hz('C7'))
stud_pitch = librosa.yin(stud_y, fmin=librosa.note_to_hz('C2'), fmax=librosa.note_to_hz('C7'))

pitch_diff = abs(prof_pitch.mean() - stud_pitch.mean())
timing_diff = abs(len(prof_pitch) - len(stud_pitch))

# === Create Graph ===
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

# === Create PDF ===
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
pdf.multi_cell(0, 10, deepgram_feedback, fill=True)

pdf.output(output_pdf)
print(f"✅ PDF saved: {output_pdf}")

# === Upload to B2 ===
print("🔐 Uploading to B2...")
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

# === Generate Signed URLs ===
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

# === Send to Zapier Webhook ===
payload_to_zapier = {
    "student_email": student_email,
    "student_url": student_url,
    "professor_url": professor_url,
    "graph_url": signed_url_graph,
    "report_url": signed_url_pdf,
    "pitch_difference": round(pitch_diff, 2),
    "timing_difference": timing_diff,
    "deepgram_feedback": deepgram_feedback
}

print(f"📡 Sending full payload to Zapier: {callback_url}")
try:
    response = requests.post(callback_url, json=payload_to_zapier)
    print(f"✅ Callback status: {response.status_code}")
    print(f"📬 Response: {response.text}")
except Exception as e:
    print(f"❌ Error sending to Zapier: {e}")
    exit(1)


