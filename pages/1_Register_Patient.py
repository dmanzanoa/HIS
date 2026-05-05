import streamlit as st
import pandas as pd
import uuid

from database import load_state, save_state
from event_engine import process_patient_arrival

st.title("🧍 Register Patient Arrival")

state = load_state()

with st.form("register_patient_form"):
    patient_name = st.text_input("Patient name")
    age = st.number_input("Age", min_value=0, max_value=120, value=45)
    gender = st.selectbox("Gender", ["Male", "Female", "Other"])
    reason = st.text_area("Reason for visit")
    acuity = st.slider("Initial acuity / priority", 1, 5, 3)

    submitted = st.form_submit_button("Register patient")

if submitted:
    encounter_id = f"LIVE_{uuid.uuid4().hex[:8]}"
    patient_id = f"P_{uuid.uuid4().hex[:8]}"
    arrival_time = pd.Timestamp.now().floor("min")

    state = process_patient_arrival(
        state=state,
        encounter_id=encounter_id,
        patient_id=patient_id,
        arrival_time=arrival_time,
        unit_id="U_ED",
        priority=acuity
    )

    state["current_patients"].loc[
        state["current_patients"]["encounter_id"] == encounter_id,
        ["name", "age", "gender", "reason", "acuity"]
    ] = [patient_name, age, gender, reason, acuity]

    save_state(state)

    st.success(f"Patient registered. Encounter ID: {encounter_id}")