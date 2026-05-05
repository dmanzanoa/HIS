# hospital_twin/app.py

import streamlit as st

st.set_page_config(
    page_title="Hospital Digital Twin HIS",
    layout="wide"
)

st.title("🏥 Hospital Information System + Digital Twin")

st.write("""
This prototype simulates a hospital HIS where users can register patients,
triage them, assign doctors, manage beds, monitor staff, and view live KPIs.
""")

st.info("Use the sidebar pages to operate the hospital.")