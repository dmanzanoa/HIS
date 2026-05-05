import streamlit as st
import pandas as pd
import numpy as np

from database import load_state, save_state
from event_engine import assign_staff_to_queue, assign_bed_live, discharge_patient, log_live_event
from kpi_engine import compute_live_kpis

st.title("👨‍⚕️ Doctor Assessment")

state = load_state()
current_time = pd.Timestamp.now().floor("min")

queue = state["current_queue_state"].copy()

physician_waiting = queue[
    (queue["queue_type"] == "physician_queue") &
    (queue["status"] == "waiting")
].copy()

st.subheader("Patients Waiting for Doctor")

if physician_waiting.empty:
    st.success("No patients waiting for doctor assessment.")
else:
    physician_waiting["entered_at"] = pd.to_datetime(physician_waiting["entered_at"], errors="coerce")
    physician_waiting["waiting_minutes"] = (
        current_time - physician_waiting["entered_at"]
    ).dt.total_seconds() / 60

    physician_waiting = physician_waiting.sort_values(
        ["priority", "entered_at"],
        ascending=[False, True]
    )

    st.dataframe(physician_waiting, use_container_width=True)

st.subheader("Available ED Physicians")

staff = state["current_staff_status"].copy()
available_physicians = staff[
    (staff["role"] == "ed_physician") &
    (staff["status"] == "available")
].copy()

st.dataframe(available_physicians, use_container_width=True)

st.subheader("Doctor Decision")

service_minutes = st.slider(
    "Assessment duration",
    min_value=10,
    max_value=60,
    value=25,
    step=5
)

decision = st.selectbox(
    "Clinical decision after assessment",
    [
        "Discharge after ED observation",
        "Admit to Medical Ward",
        "Admit to ICU"
    ]
)

if decision == "Discharge after ED observation":
    expected_los_hours = st.slider("ED observation LOS hours", 1, 12, 4)
    target_unit = "U_ED"
elif decision == "Admit to Medical Ward":
    expected_los_hours = st.slider("Medical ward expected LOS hours", 24, 168, 72)
    target_unit = "U_MED"
else:
    expected_los_hours = st.slider("ICU expected LOS hours", 24, 240, 96)
    target_unit = "U_ICU"

if st.button("Assess Next Patient", type="primary"):
    if physician_waiting.empty:
        st.warning("No physician patients waiting.")
    elif available_physicians.empty:
        st.error("No ED physician available.")
    else:
        state, physician_task = assign_staff_to_queue(
            state=state,
            queue_type="physician_queue",
            current_time=current_time,
            service_minutes=service_minutes
        )

        if physician_task is None:
            st.error("Could not assign physician.")
        else:
            encounter_id = physician_task["encounter_id"]
            patient_id = physician_task["patient_id"]
            decision_time = physician_task["task_end"]

            if decision == "Discharge after ED observation":
                state = log_live_event(
                    state,
                    decision_time,
                    "discharge_decision",
                    encounter_id=encounter_id,
                    patient_id=patient_id,
                    unit_id="U_ED",
                    details="Doctor decided discharge after ED observation"
                )

                state, bed_id = assign_bed_live(
                    state=state,
                    encounter_id=encounter_id,
                    patient_id=patient_id,
                    unit_id="U_ED",
                    request_time=decision_time,
                    expected_los_hours=expected_los_hours
                )

                new_status = "ed_observation" if bed_id is not None else "waiting_ed_bed"

            else:
                state = log_live_event(
                    state,
                    decision_time,
                    "admit_decision",
                    encounter_id=encounter_id,
                    patient_id=patient_id,
                    unit_id="U_ED",
                    details=f"Doctor decided admission to {target_unit}"
                )

                state, bed_id = assign_bed_live(
                    state=state,
                    encounter_id=encounter_id,
                    patient_id=patient_id,
                    unit_id=target_unit,
                    request_time=decision_time,
                    expected_los_hours=expected_los_hours
                )

                if bed_id is not None:
                    patient_status = state["current_patients"].loc[
                        state["current_patients"]["encounter_id"] == encounter_id,
                        "current_status"
                    ].iloc[0]

                    if patient_status == "boarding_in_ed":
                        new_status = "boarding_in_ed"
                    else:
                        new_status = "admitted"
                else:
                    new_status = "waiting_bed"

            state["current_patients"].loc[
                state["current_patients"]["encounter_id"] == encounter_id,
                ["current_status", "target_unit", "last_event_time"]
            ] = [new_status, target_unit, decision_time]

            save_state(state)

            st.success(
                f"Assessment completed for encounter {encounter_id}. "
                f"Decision: {decision}."
            )

st.divider()
st.subheader("Current KPIs")

kpis = compute_live_kpis(state)
sys = kpis["system_kpi"].iloc[0]

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Active Patients", int(sys["active_patients"]))
c2.metric("Waiting Patients", int(sys["waiting_patients"]))
c3.metric("Occupied Beds", int(sys["occupied_beds"]))
c4.metric("Busy Staff", int(sys["busy_staff"]))
c5.metric("ED Boarders", int(sys["ed_boarders"]))

st.subheader("Recent Events")
events = state["live_event_log"].copy()

if events.empty:
    st.info("No events yet.")
else:
    st.dataframe(events.tail(30), use_container_width=True)