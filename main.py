import os
import json
import streamlit as st
from google.oauth2 import service_account
from googleapiclient.discovery import build

# Load credentials from the full service account JSON stored in one environment variable
service_account_info = json.loads(os.environ["GOOGLE_SERVICE_ACCOUNT_JSON"])
credentials = service_account.Credentials.from_service_account_info(service_account_info)

# Setup Google Drive API client
@st.cache_resource
def setup_drive():
    return build("drive", "v3", credentials=credentials)

drive_service = setup_drive()

# Streamlit UI
st.title("AI Quartet Singing Evaluation")

student_email = st.text_input("Student Email")
student_audio_url = st.text_input("Student Audio URL (Google Drive share link)")
professor_audio_url = st.text_input("Professor Audio URL (Google Drive share link)")

if st.button("Submit for Evaluation"):
    if not all([student_email, student_audio_url, professor_audio_url]):
        st.warning("Please fill in all fields.")
    else:
        # You can add transcription and analysis logic here
        st.success("✅ Submission received.")
        st.write("Student Email:", student_email)
        st.write("Student Audio URL:", student_audio_url)
        st.write("Professor Audio URL:", professor_audio_url)

        # Example output to return to Zapier if needed
        result = {
            "email": student_email,
            "student_url": student_audio_url,
            "professor_url": professor_audio_url,
            "status": "Evaluation complete (mock result)"  # Replace with real logic
        }
        st.json(result)

