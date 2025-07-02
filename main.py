import os
import uuid
from flask import Flask, request, jsonify
from b2sdk.v2 import InMemoryAccountInfo, B2Api
from datetime import timedelta

# Set up Backblaze B2 credentials from environment
B2_KEY_ID = os.getenv("B2_KEY_ID")
B2_APPLICATION_KEY = os.getenv("B2_APPLICATION_KEY")
B2_BUCKET_NAME = os.getenv("B2_BUCKET_NAME")

# Backblaze B2 SDK setup
info = InMemoryAccountInfo()
b2_api = B2Api(info)
b2_api.authorize_account("production", B2_KEY_ID, B2_APPLICATION_KEY)
bucket = b2_api.get_bucket_by_name(B2_BUCKET_NAME)

app = Flask(__name__)

@app.route("/webhook", methods=["POST"])
def handle_webhook():
    data = request.get_json()

    # Simulated inputs: replace with your own file creation logic
    pitch_diff = data.get("pitch_difference", 0.0)
    timing_diff = data.get("timing_difference", 0.0)
    graph_content = f"Pitch: {pitch_diff}\nTiming: {timing_diff}"
    graph_filename = f"graph_{uuid.uuid4().hex}.txt"

    # Upload the graph content as a file
    try:
        file_info = {
            "description": "Evaluation graph",
            "contentType": "text/plain"
        }
        b2_file = bucket.upload_bytes(
            data_bytes=graph_content.encode("utf-8"),
            file_name=graph_filename,
            content_type="text/plain",
            file_info=file_info
        )

        # Create a signed URL valid for 24 hours
        signed_url = b2_api.get_download_authorization(
            bucket_id=bucket.id_,
            file_name=graph_filename,
            valid_duration_seconds=86400  # 24 hours
        )

        file_url = f"https://f000.backblazeb2.com/file/{B2_BUCKET_NAME}/{graph_filename}?Authorization={signed_url.authorization_token}"

        return jsonify({
            "pitch_difference": pitch_diff,
            "timing_difference": timing_diff,
            "graph_url": file_url
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/", methods=["GET"])
def index():
    return "AI Quartet Evaluator is running."

if __name__ == "__main__":
    app.run(debug=False, host="0.0.0.0", port=int(os.getenv("PORT", 10000)))
