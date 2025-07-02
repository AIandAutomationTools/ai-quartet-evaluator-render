import os
import io
import base64
from flask import Flask, request, jsonify
import matplotlib.pyplot as plt
from datetime import datetime, timedelta
from b2sdk.v2 import InMemoryAccountInfo, B2Api

# Initialize Flask
app = Flask(__name__)

# Load environment variables
B2_KEY_ID = os.environ.get("B2_KEY_ID")
B2_APPLICATION_KEY = os.environ.get("B2_APPLICATION_KEY")
B2_BUCKET_NAME = os.environ.get("B2_BUCKET_NAME")

# Authorize and get B2 bucket
info = InMemoryAccountInfo()
b2_api = B2Api(info)
b2_api.authorize_account("production", B2_KEY_ID, B2_APPLICATION_KEY)
bucket = b2_api.get_bucket_by_name(B2_BUCKET_NAME)

def upload_chart_to_b2(pitch_diff, timing_diff):
    try:
        # Generate the chart
        fig, ax = plt.subplots()
        ax.bar(['Pitch', 'Timing'], [pitch_diff, timing_diff], color=['blue', 'green'])
        ax.set_ylabel('Difference')
        ax.set_title('Pitch and Timing Differences')

        # Save to bytes buffer
        buffer = io.BytesIO()
        plt.savefig(buffer, format='png')
        buffer.seek(0)

        # Generate unique filename
        filename = f"chart_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.png"

        # Upload to B2
        file_info = {
            'created': datetime.utcnow().isoformat()
        }
        uploaded_file = bucket.upload_bytes(buffer.read(), filename, file_info=file_info)

        # Generate signed URL valid for 24 hours
        url = bucket.get_download_url_by_id(uploaded_file.id_)
        signed_url = b2_api.get_download_authorization(
            bucket_id=bucket.id_,
            file_name=filename,
            valid_duration_in_seconds=24 * 3600
        )

        return f"{url}?Authorization={signed_url.authorization_token}"
    except Exception as e:
        print("Upload error:", str(e))
        return "Upload failed."

@app.route('/')
def home():
    return "AI Quartet Evaluator is running."

@app.route('/webhook', methods=['POST'])
def handle_webhook():
    data = request.json
    student_email = data.get("student_email")
    pitch_diff = data.get("pitch_difference", 0)
    timing_diff = data.get("timing_difference", 0)

    print("Received data:", data)

    # Upload the chart and get the secure URL
    chart_url = upload_chart_to_b2(pitch_diff, timing_diff)

    return jsonify({
        "student_email": student_email,
        "pitch_difference": pitch_diff,
        "timing_difference": timing_diff,
        "graph_url": chart_url
    })

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
