import os
import json
import streamlit as st
from google.oauth2 import service_account
from googleapiclient.discovery import build
import urllib.request

# Load credentials from environment variable
service_account_info = json.loads(os.environ["GOOGLE_SERVICE_ACCOUNT_JSON"])
credentials = service_account.Credentials.from_service_account_info(service_account_info)

@st.cache_resource
def setup_drive():
    return build("drive", "v3", credentials=credentials)

drive_service = setup_drive()

# Streamlit UI
st.title("AI Quartet Singing Evaluation")

# Handle JSON POST if from Zapier
if st.runtime.exists():
    if "REQUEST_METHOD" in os.environ and os.environ["REQUEST_METHOD"] == "POST":
        # Read body (from Zapier)
        request_body = st.request.body.decode("utf-8")
        data = json.loads(request_body)

        student_email = data.get("email")
        student_audio_url = data.get("student_url")
        professor_audio_url = data.get("professor_url")

        result = {
            "email": student_email,
            "student_url": student_audio_url,
            "professor_url": professor_audio_url,
            "status": "Evaluation complete (mock result)"
        }

        st.json(result)  # Response to Zapier
    else:
        # Manual test mode
        student_email = st.text_input("Student Email")
        student_audio_url = st.text_input("Student Audio URL (Google Drive share link)")
        professor_audio_url = st.text_input("Professor Audio URL (Google Drive share link)")

        if st.button("Submit for Evaluation"):
            result = {
                "email": student_email,
                "student_url": student_audio_url,
                "professor_url": professor_audio_url,
                "status": "Evaluation complete (mock result)"
            }
            st.success("✅ Submission received.")
            st.json(result)

