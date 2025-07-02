import os
from b2sdk.v2 import InMemoryAccountInfo, B2Api
from b2sdk.v2.exception import InvalidAuthToken

# === Load environment variables ===
print("🔄 Loading environment variables...")

B2_KEY_ID = os.getenv("B2_KEY_ID")
B2_APPLICATION_KEY = os.getenv("B2_APP_KEY")  # ✅ Your custom environment var
B2_BUCKET_NAME = os.getenv("B2_BUCKET_NAME")

print("\n🔍 Debug info:")
print(f"✅ B2_KEY_ID: {B2_KEY_ID}")
print(f"✅ B2_BUCKET_NAME: {B2_BUCKET_NAME}")
print(f"✅ B2_APPLICATION_KEY length: {len(B2_APPLICATION_KEY) if B2_APPLICATION_KEY else 'None'}")

if not B2_KEY_ID or not B2_APPLICATION_KEY or not B2_BUCKET_NAME:
    print("❌ ERROR: One or more environment variables are missing!")
    exit(1)

# === Authorize with Backblaze B2 ===
try:
    print("\n🔐 Authorizing with Backblaze B2...")
    info = InMemoryAccountInfo()
    b2_api = B2Api(info)
    b2_api.authorize_account("production", B2_KEY_ID, B2_APPLICATION_KEY)
    print("✅ Authorized successfully!")

    # === Locate or create the bucket ===
    bucket = b2_api.get_bucket_by_name(B2_BUCKET_NAME)
    if not bucket:
        print(f"❌ ERROR: Bucket '{B2_BUCKET_NAME}' not found!")
        exit(1)
    print(f"📦 Using bucket: {bucket.name}")

    # === Upload a test file ===
    test_filename = "test_upload.txt"
    with open(test_filename, "w") as f:
        f.write("This is a test upload from main.py.\n")

    print(f"📤 Uploading {test_filename} to {bucket.name}...")
    bucket.upload_local_file(
        local_file=test_filename,
        file_name=test_filename,
    )
    print("✅ Upload succeeded.")

except InvalidAuthToken as e:
    print("❌ Authorization failed.")
    print(f"Exception: {e}")
    exit(1)

except Exception as e:
    print("❌ An unexpected error occurred.")
    print(f"Exception: {e}")
    exit(1)


