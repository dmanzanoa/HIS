import streamlit as st
import pandas as pd
import numpy as np

from database import load_state, save_state
from event_engine import assign_staff_to_queue, assign_bed_live, discharge_patient, log_live_event
from kpi_engine import compute_live_kpis

st.title("🛏️ Bed Manager")

state = load_state()
current_time = pd.Timestamp.now().floor("min")

# ---------------------------------------------------------
# Basic tables
# ---------------------------------------------------------
patients = state["current_patients"].copy()
beds = state["current_bed_status"].copy()
queue = state["current_queue_state"].copy()

# ---------------------------------------------------------
# KPIs
# ---------------------------------------------------------
st.subheader("Current Bed KPIs")

kpis = compute_live_kpis(state)
sys = kpis["system_kpi"].iloc[0]

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Active Patients", int(sys["active_patients"]))
c2.metric("Waiting Patients", int(sys["waiting_patients"]))
c3.metric("Occupied Beds", int(sys["occupied_beds"]))
c4.metric("ED Boarders", int(sys["ed_boarders"]))
c5.metric("Discharge-Ready Waiting", int(sys.get("discharge_ready_but_waiting", 0)))

st.dataframe(kpis["bed_kpi"], use_container_width=True)

st.divider()

# ---------------------------------------------------------
# Bed queue
# ---------------------------------------------------------
st.subheader("Patients Waiting for Beds")

if queue.empty:
    bed_queue = pd.DataFrame()
else:
    bed_queue = queue[
        (queue["queue_type"] == "bed_queue") &
        (queue["status"] == "waiting")
    ].copy()

if bed_queue.empty:
    st.success("No patients waiting for beds.")
else:
    bed_queue["entered_at"] = pd.to_datetime(bed_queue["entered_at"], errors="coerce")
    bed_queue["waiting_minutes"] = (
        current_time - bed_queue["entered_at"]
    ).dt.total_seconds() / 60

    bed_queue = bed_queue.sort_values(
        ["priority", "entered_at"],
        ascending=[False, True]
    )

    st.dataframe(bed_queue, use_container_width=True)

# ---------------------------------------------------------
# Available beds
# ---------------------------------------------------------
st.subheader("Available Beds by Unit")

available_beds = beds[beds["status"] == "available"].copy()

available_summary = (
    available_beds.groupby("unit_id")
    .size()
    .reset_index(name="available_beds")
    if not available_beds.empty
    else pd.DataFrame(columns=["unit_id", "available_beds"])
)

st.dataframe(available_summary, use_container_width=True)

# ---------------------------------------------------------
# Process next bed queue item
# ---------------------------------------------------------
st.subheader("Process Next Bed Request")

if not bed_queue.empty:
    selected_queue_id = st.selectbox(
        "Select bed request",
        bed_queue["queue_id"].tolist()
    )

    selected_request = bed_queue[
        bed_queue["queue_id"] == selected_queue_id
    ].iloc[0]

    default_unit = selected_request["unit_id"]

    target_unit = st.selectbox(
        "Target unit",
        ["U_ED", "U_MED", "U_ICU", "U_SURG"],
        index=["U_ED", "U_MED", "U_ICU", "U_SURG"].index(default_unit)
        if default_unit in ["U_ED", "U_MED", "U_ICU", "U_SURG"] else 0
    )

    expected_los_hours = st.slider(
        "Expected LOS hours",
        min_value=1,
        max_value=240,
        value=72 if target_unit in ["U_MED", "U_ICU"] else 8
    )

    if st.button("Assign Bed / Process Request", type="primary"):
        state, bed_task = assign_staff_to_queue(
            state=state,
            queue_type="bed_queue",
            current_time=current_time,
            service_minutes=10
        )

        if bed_task is None:
            st.error("No bed manager available or no processable bed queue.")
        else:
            encounter_id = selected_request["encounter_id"]
            patient_id = selected_request["patient_id"]

            state, bed_id = assign_bed_live(
                state=state,
                encounter_id=encounter_id,
                patient_id=patient_id,
                unit_id=target_unit,
                request_time=current_time,
                expected_los_hours=expected_los_hours
            )

            if bed_id is not None:
                state["current_queue_state"].loc[
                    state["current_queue_state"]["queue_id"] == selected_queue_id,
                    "status"
                ] = "completed"

                state = log_live_event(
                    state,
                    current_time,
                    "bed_manager_assigned_bed",
                    encounter_id=encounter_id,
                    patient_id=patient_id,
                    unit_id=target_unit,
                    bed_id=bed_id,
                    details=f"Bed manager assigned {bed_id}"
                )

                save_state(state)
                st.success(f"Assigned bed {bed_id} to encounter {encounter_id}.")
            else:
                save_state(state)
                st.warning("No bed available. Patient remains waiting or boarding.")

# ---------------------------------------------------------
# ED boarders
# ---------------------------------------------------------
st.divider()
st.subheader("ED Boarders")

if patients.empty or "current_status" not in patients.columns:
    boarders = pd.DataFrame()
else:
    boarders = patients[
        patients["current_status"] == "boarding_in_ed"
    ].copy()

if boarders.empty:
    st.success("No ED boarders.")
else:
    st.dataframe(boarders, use_container_width=True)

    selected_boarder = st.selectbox(
        "Select ED boarder to transfer",
        boarders["encounter_id"].tolist()
    )

    boarder_row = boarders[
        boarders["encounter_id"] == selected_boarder
    ].iloc[0]

    target_unit = boarder_row.get("target_unit", "U_MED")

    available_target_beds = beds[
        (beds["unit_id"] == target_unit) &
        (beds["status"] == "available")
    ].copy()

    st.write(f"Target unit: `{target_unit}`")
    st.write(f"Available target beds: {len(available_target_beds)}")

    if st.button("Transfer Boarder to Target Unit"):
        if available_target_beds.empty:
            st.error(f"No available beds in {target_unit}.")
        else:
            old_bed_id = boarder_row.get("assigned_bed_id", None)
            new_bed = available_target_beds.sort_values("bed_id").iloc[0]
            new_bed_id = new_bed["bed_id"]

            expected_los_hours = 72 if target_unit == "U_MED" else 120
            clinically_ready_time = current_time + pd.to_timedelta(expected_los_hours, unit="h")
            expected_release_time = clinically_ready_time + pd.to_timedelta(np.random.uniform(2, 12), unit="h")

            # release old ED bed
            if pd.notna(old_bed_id):
                state["current_bed_status"].loc[
                    state["current_bed_status"]["bed_id"] == old_bed_id,
                    ["status", "encounter_id", "patient_id", "occupied_since", "expected_release_time", "clinically_ready_time"]
                ] = ["available", None, None, pd.NaT, pd.NaT, pd.NaT]

            # occupy target bed
            state["current_bed_status"].loc[
                state["current_bed_status"]["bed_id"] == new_bed_id,
                ["status", "encounter_id", "patient_id", "occupied_since", "expected_release_time", "clinically_ready_time"]
            ] = [
                "occupied",
                boarder_row["encounter_id"],
                boarder_row["patient_id"],
                current_time,
                expected_release_time,
                clinically_ready_time
            ]

            # update patient
            state["current_patients"].loc[
                state["current_patients"]["encounter_id"] == boarder_row["encounter_id"],
                ["current_unit", "current_status", "assigned_bed_id", "boarding_flag", "last_event_time"]
            ] = [target_unit, "in_bed", new_bed_id, 0, current_time]

            state = log_live_event(
                state,
                current_time,
                "transfer_from_ed_boarding",
                encounter_id=boarder_row["encounter_id"],
                patient_id=boarder_row["patient_id"],
                unit_id=target_unit,
                bed_id=new_bed_id,
                details=f"Transferred from ED bed {old_bed_id} to {target_unit}"
            )

            save_state(state)
            st.success(f"Transferred patient to {new_bed_id}.")

# ---------------------------------------------------------
# Manual discharge
# ---------------------------------------------------------
st.divider()
st.subheader("Manual Discharge")

if patients.empty:
    active_patients = pd.DataFrame()
else:
    active_patients = patients[
        patients["current_status"] != "discharged"
    ].copy()

if active_patients.empty:
    st.info("No active patients to discharge.")
else:
    selected_discharge = st.selectbox(
        "Select patient encounter to discharge",
        active_patients["encounter_id"].tolist()
    )

    if st.button("Discharge Patient"):
        state = discharge_patient(
            state=state,
            encounter_id=selected_discharge,
            discharge_time=current_time
        )

        save_state(state)
        st.success(f"Patient {selected_discharge} discharged.")

# ---------------------------------------------------------
# Recent events
# ---------------------------------------------------------
st.divider()
st.subheader("Recent Bed Events")

events = state["live_event_log"].copy()

if events.empty:
    st.info("No events yet.")
else:
    bed_events = events[
        events["event_type"].astype(str).str.contains(
            "bed|boarding|transfer|discharge",
            case=False,
            na=False
        )
    ].copy()

    st.dataframe(bed_events.tail(50), use_container_width=True)