import os
import io
from flask import Flask, request, jsonify
import matplotlib.pyplot as plt
from b2sdk.v2 import InMemoryAccountInfo, B2Api
import uuid
import numpy as np

app = Flask(__name__)

# === Load environment variables ===
print("=== Starting B2 Upload Service ===")
print("Loading environment variables...")

B2_KEY_ID = os.environ.get("B2_KEY_ID")
B2_APPLICATION_KEY = os.environ.get("B2_APPLICATION_KEY")
B2_BUCKET_NAME = os.environ.get("B2_BUCKET_NAME")

# Debug info
if not B2_KEY_ID:
    print("❌ ERROR: B2_KEY_ID is not set!")
if not B2_APPLICATION_KEY:
    print("❌ ERROR: B2_APPLICATION_KEY is not set!")
if not B2_BUCKET_NAME:
    print("❌ ERROR: B2_BUCKET_NAME is not set!")

print(f"B2_KEY_ID: {B2_KEY_ID}")
print(f"B2_BUCKET_NAME: {B2_BUCKET_NAME}")
print(f"B2_APPLICATION_KEY length: {len(B2_APPLICATION_KEY) if B2_APPLICATION_KEY else 'None'}")

# === Authorize with Backblaze B2 ===
info = InMemoryAccountInfo()
b2_api = B2Api(info)

print("Authorizing with Backblaze B2...")
try:
    b2_api.authorize_account("https://api.backblazeb2.com", B2_KEY_ID, B2_APPLICATION_KEY)
    print("✅ Authorization successful.")
except Exception as e:
    print("❌ Authorization failed.")
    print(f"Exception: {e}")
    raise

bucket = b2_api.get_bucket_by_name(B2_BUCKET_NAME)

# === Flask Route for Upload ===
@app.route('/upload', methods=['POST'])
def upload_image():
    try:
        data = request.get_json()
        label = data.get('label', 'default')
        print(f"Received label: {label}")

        # === Generate plot ===
        fig, ax = plt.subplots()
        x = np.linspace(0, 2 * np.pi, 100)
        y = np.sin(x)
        ax.plot(x, y, label=label)
        ax.legend()

        # Save image to memory
        img_bytes = io.BytesIO()
        plt.savefig(img_bytes, format='png')
        plt.close(fig)
        img_bytes.seek(0)

        # Generate unique file name
        file_name = f"plot_{uuid.uuid4().hex}.png"

        # === Upload to B2 ===
        print(f"Uploading file: {file_name}")
        bucket.upload_bytes(img_bytes.read(), file_name)
        print("✅ Upload succeeded.")

        # Return URL
        download_url = f"https://f000.backblazeb2.com/file/{B2_BUCKET_NAME}/{file_name}"
        return jsonify({'message': 'Upload successful', 'url': download_url}), 200

    except Exception as e:
        print(f"❌ Upload failed: {e}")
        return jsonify({'error': str(e)}), 500

# === Health check ===
@app.route('/', methods=['GET'])
def health_check():
    return "Service is running", 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)

