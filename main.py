import os
import librosa
import matplotlib.pyplot as plt
from b2sdk.v2 import InMemoryAccountInfo, B2Api
from b2sdk.v2.exception import InvalidAuthToken

# === Load environment variables ===
print("🔄 Loading environment variables...")

B2_KEY_ID = os.getenv("B2_KEY_ID")
B2_APPLICATION_KEY = os.getenv("B2_APP_KEY")  # Your custom environment var
B2_BUCKET_NAME = os.getenv("B2_BUCKET_NAME")

print("\n🔍 Debug info:")
print(f"✅ B2_KEY_ID: {B2_KEY_ID}")
print(f"✅ B2_BUCKET_NAME: {B2_BUCKET_NAME}")
print(f"✅ B2_APPLICATION_KEY length: {len(B2_APPLICATION_KEY) if B2_APPLICATION_KEY else 'None'}")

if not B2_KEY_ID or not B2_APPLICATION_KEY or not B2_BUCKET_NAME:
    print("❌ ERROR: Missing env vars")
    exit(1)

# === File paths ===
professor_file = "professor.mp3"
student_file = "student.mp3"
output_graph = "output_graph.png"

# === Validate that files exist ===
for f in [professor_file, student_file]:
    if not os.path.exists(f):
        print(f"❌ Missing required file: {f}")
        exit(1)

# === Load audio files ===
print("🔊 Loading audio...")
prof_y, prof_sr = librosa.load(professor_file)
stud_y, stud_sr = librosa.load(student_file)

# === Extract pitch using librosa.yin
print("🎼 Extracting pitch...")
prof_pitch = librosa.yin(prof_y, fmin=librosa.note_to_hz('C2'), fmax=librosa.note_to_hz('C7'))
stud_pitch = librosa.yin(stud_y, fmin=librosa.note_to_hz('C2'), fmax=librosa.note_to_hz('C7'))

# === Plot the pitch contours ===
print("📊 Plotting graph...")
plt.figure(figsize=(10, 4))
plt.plot(prof_pitch, label="Professor", alpha=0.7)
plt.plot(stud_pitch, label="Student", alpha=0.7)
plt.legend()
plt.title("Pitch Comparison")
plt.xlabel("Time Frame")
plt.ylabel("Frequency (Hz)")
plt.tight_layout()
plt.savefig(output_graph)
print(f"✅ Graph saved as {output_graph}")

# === Upload to Backblaze B2 ===
try:
    print("🔐 Authorizing with B2...")
    info = InMemoryAccountInfo()
    b2_api = B2Api(info)
    b2_api.authorize_account("production", B2_KEY_ID, B2_APPLICATION_KEY)
    print("✅ Authorized")

    bucket = b2_api.get_bucket_by_name(B2_BUCKET_NAME)
    if not bucket:
        print(f"❌ Bucket '{B2_BUCKET_NAME}' not found!")
        exit(1)

    print(f"📤 Uploading {output_graph} to bucket...")
    bucket.upload_local_file(
        local_file=output_graph,
        file_name=output_graph,
    )
    print("✅ Upload complete.")

except InvalidAuthToken as e:
    print("❌ Auth failed:", e)
    exit(1)
except Exception as e:
    print("❌ Unexpected error:", e)
    exit(1)
