import os
import requests
from flask import Flask, request, jsonify

app = Flask(__name__)

def download_file(url, filename):
    url = url.strip()  # Remove leading/trailing spaces just in case
    print(f"🌐 Downloading from: {url}")
    response = requests.get(url)
    if response.status_code == 200:
        with open(filename, "wb") as f:
            f.write(response.content)
        print(f"📁 {filename} saved ({len(response.content)} bytes)")
        return True
    else:
        print(f"❌ Failed to download {url}, status code: {response.status_code}")
        return False

@app.route("/", methods=["POST"])
def evaluate():
    data = request.json
    print(f"📥 Incoming request: {data}")

    email = data.get("email")
    student_url = data.get("student_url")
    professor_url = data.get("professor_url")

    if not all([email, student_url, professor_url]):
        return jsonify({"error": "Missing one of the required fields: email, student_url, professor_url"}), 400

    # Download files
    if not download_file(student_url, "student.mp3"):
        return jsonify({"error": "Failed to download student mp3 file"}), 400
    if not download_file(professor_url, "professor.mp3"):
        return jsonify({"error": "Failed to download professor mp3 file"}), 400

    # Here you can add your audio processing and evaluation logic
    # For now, just return a success message

    return jsonify({"message": "Files downloaded successfully", "email": email})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))  # Render sets PORT environment variable
    app.run(host="0.0.0.0", port=port)

