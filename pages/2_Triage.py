import streamlit as st
import pandas as pd
import numpy as np

from database import load_state, save_state
from event_engine import assign_staff_to_queue, log_live_event
from kpi_engine import compute_live_kpis

st.title("🩺 Triage Queue")

state = load_state()
current_time = pd.Timestamp.now().floor("min")

# ---------------------------------------------------------
# Waiting triage queue
# ---------------------------------------------------------
queue = state["current_queue_state"].copy()

triage_waiting = queue[
    (queue["queue_type"] == "triage_queue") &
    (queue["status"] == "waiting")
].copy()

st.subheader("Patients Waiting for Triage")

if triage_waiting.empty:
    st.success("No patients waiting for triage.")
else:
    triage_waiting["entered_at"] = pd.to_datetime(triage_waiting["entered_at"], errors="coerce")
    triage_waiting["waiting_minutes"] = (
        current_time - triage_waiting["entered_at"]
    ).dt.total_seconds() / 60

    triage_waiting = triage_waiting.sort_values(
        ["priority", "entered_at"],
        ascending=[False, True]
    )

    st.dataframe(triage_waiting, use_container_width=True)

# ---------------------------------------------------------
# Staff availability
# ---------------------------------------------------------
st.subheader("Available Triage Nurses")

staff = state["current_staff_status"].copy()
available_triage = staff[
    (staff["role"] == "triage_nurse") &
    (staff["status"] == "available")
].copy()

st.dataframe(available_triage, use_container_width=True)

# ---------------------------------------------------------
# Process next triage
# ---------------------------------------------------------
st.subheader("Process Triage")

service_minutes = st.slider(
    "Triage service duration",
    min_value=5,
    max_value=30,
    value=12,
    step=1
)

if st.button("Process Next Triage Patient", type="primary"):
    if triage_waiting.empty:
        st.warning("No triage patients waiting.")
    elif available_triage.empty:
        st.error("No triage nurse available.")
    else:
        state, triage_task = assign_staff_to_queue(
            state=state,
            queue_type="triage_queue",
            current_time=current_time,
            service_minutes=service_minutes
        )

        if triage_task is None:
            st.error("Could not assign triage staff.")
        else:
            encounter_id = triage_task["encounter_id"]
            patient_id = triage_task["patient_id"]
            triage_end = triage_task["task_end"]

            patient_row = state["current_patients"][
                state["current_patients"]["encounter_id"] == encounter_id
            ]

            if not patient_row.empty and "acuity" in patient_row.columns:
                acuity = patient_row.iloc[0].get("acuity", 3)
                if pd.isna(acuity):
                    acuity = 3
                acuity = int(acuity)
            else:
                acuity = 3

            # Create physician queue after triage
            physician_queue_id = f"Q_DOC_{encounter_id}"

            already_exists = (
                state["current_queue_state"]["queue_id"] == physician_queue_id
            ).any()

            if not already_exists:
                physician_queue_row = pd.DataFrame([{
                    "queue_id": physician_queue_id,
                    "encounter_id": encounter_id,
                    "patient_id": patient_id,
                    "queue_type": "physician_queue",
                    "unit_id": "U_ED",
                    "role_required": "ed_physician",
                    "entered_at": triage_end,
                    "priority": acuity,
                    "status": "waiting"
                }])

                state["current_queue_state"] = pd.concat(
                    [state["current_queue_state"], physician_queue_row],
                    ignore_index=True
                )

                state = log_live_event(
                    state,
                    triage_end,
                    "entered_physician_queue",
                    encounter_id=encounter_id,
                    patient_id=patient_id,
                    unit_id="U_ED",
                    details="Patient completed triage and entered physician queue"
                )

            state["current_patients"].loc[
                state["current_patients"]["encounter_id"] == encounter_id,
                ["current_status", "last_event_time"]
            ] = ["waiting_physician", triage_end]

            save_state(state)

            st.success(
                f"Triage completed for encounter {encounter_id}. "
                f"Patient sent to physician queue."
            )

# ---------------------------------------------------------
# KPIs
# ---------------------------------------------------------
st.divider()
st.subheader("Current System KPIs")

kpis = compute_live_kpis(state)

c1, c2, c3, c4 = st.columns(4)
sys = kpis["system_kpi"].iloc[0]

c1.metric("Active Patients", int(sys["active_patients"]))
c2.metric("Waiting Patients", int(sys["waiting_patients"]))
c3.metric("Occupied Beds", int(sys["occupied_beds"]))
c4.metric("Busy Staff", int(sys["busy_staff"]))

st.subheader("Recent Events")
events = state["live_event_log"].copy()

if events.empty:
    st.info("No events yet.")
else:
    st.dataframe(events.tail(20), use_container_width=True)