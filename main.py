import os
import io
from flask import Flask, request, jsonify
import matplotlib.pyplot as plt
from b2sdk.v2 import InMemoryAccountInfo, B2Api
import uuid
import numpy as np

# Load environment variables
B2_KEY_ID = os.environ.get("B2_KEY_ID")
B2_APPLICATION_KEY = os.environ.get("B2_APPLICATION_KEY")
B2_BUCKET_NAME = os.environ.get("B2_BUCKET_NAME")

# Authorize B2
info = InMemoryAccountInfo()
b2_api = B2Api(info)
b2_api.authorize_account("https://api.backblazeb2.com", B2_KEY_ID, B2_APPLICATION_KEY)
bucket = b2_api.get_bucket_by_name(B2_BUCKET_NAME)

# Set up Flask
app = Flask(__name__)

@app.route("/", methods=["GET"])
def health_check():
    return "OK", 200

@app.route("/webhook", methods=["POST"])
def process_webhook():
    data = request.json
    student_pitch = data.get("student_pitch", [])
    reference_pitch = data.get("reference_pitch", [])
    student_time = data.get("student_time", [])
    reference_time = data.get("reference_time", [])

    if not (student_pitch and reference_pitch and student_time and reference_time):
        return jsonify({"error": "Missing data"}), 400

    pitch_diff = float(np.mean(np.abs(np.array(student_pitch) - np.array(reference_pitch))))
    time_diff = float(np.mean(np.abs(np.array(student_time) - np.array(reference_time))))

    # Plotting
    fig, axs = plt.subplots(2, 1, figsize=(10, 6))

    axs[0].plot(reference_pitch, label='Reference Pitch')
    axs[0].plot(student_pitch, label='Student Pitch', linestyle='--')
    axs[0].legend()
    axs[0].set_title("Pitch Comparison")

    axs[1].plot(reference_time, label='Reference Timing')
    axs[1].plot(student_time, label='Student Timing', linestyle='--')
    axs[1].legend()
    axs[1].set_title("Timing Comparison")

    plt.tight_layout()
    buf = io.BytesIO()
    plt.savefig(buf, format='png')
    buf.seek(0)

    # Upload graph to B2
    graph_filename = f"{uuid.uuid4()}.png"
    bucket.upload_bytes(buf.read(), graph_filename)
    signed_url = bucket.get_download_url_by_name(
        graph_filename,
        authorization_token=b2_api.get_download_authorization(
            B2_BUCKET_NAME, graph_filename, 3600
        )
    )

    return jsonify({
        "Pitch Difference": pitch_diff,
        "Timing Difference": time_diff,
        "Graph": signed_url
    }), 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)

