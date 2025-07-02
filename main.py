import os
from b2sdk.v2 import InMemoryAccountInfo, B2Api
from b2sdk.exception import InvalidAuthToken

# Load environment variables
print("🔄 Loading environment variables...")
B2_KEY_ID = os.getenv("B2_KEY_ID")
B2_APPLICATION_KEY = os.getenv("B2_APP_KEY")  # ✅ corrected name
B2_BUCKET_NAME = os.getenv("B2_BUCKET_NAME")

print("🔍 Debug info:")
print(f"✅ B2_KEY_ID: {B2_KEY_ID}")
print(f"✅ B2_BUCKET_NAME: {B2_BUCKET_NAME}")
print(f"✅ B2_APPLICATION_KEY length: {len(B2_APPLICATION_KEY) if B2_APPLICATION_KEY else 'None'}")

if not B2_APPLICATION_KEY:
    print("❌ ERROR: B2_APP_KEY is not set!")
    exit(1)

# Authorize and upload
try:
    print("🔐 Authorizing with Backblaze B2...")
    info = InMemoryAccountInfo()
    b2_api = B2Api(info)
    b2_api.authorize_account("production", B2_KEY_ID, B2_APPLICATION_KEY)
    print("✅ Authorized successfully!")

    # Your upload logic here...

except InvalidAuthToken as e:
    print("❌ Authorization failed.")
    print(f"Exception: {e}")
    exit(1)


