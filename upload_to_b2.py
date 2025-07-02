# upload_to_b2.py
import os
from b2sdk.v2 import InMemoryAccountInfo, B2Api
from pathlib import Path

# Load secrets
key_id = os.environ.get("B2_KEY_ID")
application_key = os.environ.get("B2_APPLICATION_KEY")
bucket_name = os.environ.get("B2_BUCKET_NAME")

# File to upload
file_path = Path("output_graph.png")  # or whatever your file is
upload_name = file_path.name

if not file_path.exists():
    raise FileNotFoundError(f"File not found: {file_path}")

# Initialize B2
info = InMemoryAccountInfo()
b2_api = B2Api(info)
b2_api.authorize_account("production", key_id, application_key)
bucket = b2_api.get_bucket_by_name(bucket_name)

# Upload
bucket.upload_local_file(
    local_file=str(file_path),
    file_name=upload_name
)
print(f"✅ Uploaded {upload_name} to B2 bucket '{bucket_name}'")
