# hospital_twin/event_engine.py

import pandas as pd
import numpy as np

def log_live_event(state, event_time, event_type, encounter_id=None,
                   patient_id=None, unit_id=None, staff_id=None,
                   bed_id=None, details=None):
    row = pd.DataFrame([{
        "event_time": pd.Timestamp(event_time),
        "event_type": event_type,
        "encounter_id": encounter_id,
        "patient_id": patient_id,
        "unit_id": unit_id,
        "staff_id": staff_id,
        "bed_id": bed_id,
        "details": details
    }])

    if state["live_event_log"].empty:
        state["live_event_log"] = row
    else:
        state["live_event_log"] = pd.concat(
            [state["live_event_log"], row],
            ignore_index=True
        )

    state["clock"] = pd.Timestamp(event_time)
    return state

def process_patient_arrival(state, encounter_id, patient_id, arrival_time, unit_id, priority=3):

    arrival_time = pd.Timestamp(arrival_time)

    # Add patient
    new_patient = pd.DataFrame([{
        "encounter_id": encounter_id,
        "patient_id": patient_id,
        "current_status": "waiting_triage",
        "unit_id": unit_id,
        "priority": priority,
        "arrival_time": arrival_time,
        "last_event_time": arrival_time
    }])

    state["current_patients"] = pd.concat(
        [state["current_patients"], new_patient],
        ignore_index=True
    )

    # Add triage queue
    queue_row = pd.DataFrame([{
        "queue_id": f"Q_TRIAGE_{encounter_id}",
        "encounter_id": encounter_id,
        "patient_id": patient_id,
        "queue_type": "triage_queue",
        "unit_id": unit_id,
        "role_required": "triage_nurse",
        "entered_at": arrival_time,
        "priority": priority,
        "status": "waiting"
    }])

    state["current_queue_state"] = pd.concat(
        [state["current_queue_state"], queue_row],
        ignore_index=True
    )

    state = log_live_event(
        state,
        arrival_time,
        "arrival",
        encounter_id=encounter_id,
        patient_id=patient_id,
        unit_id=unit_id
    )

    return state


def assign_staff_to_queue(state, queue_type, current_time, service_minutes):

    queue = state["current_queue_state"]
    staff = state["current_staff_status"]

    current_time = pd.Timestamp(current_time)

    waiting = queue[
        (queue["queue_type"] == queue_type) &
        (queue["status"] == "waiting") &
        (pd.to_datetime(queue["entered_at"], errors="coerce") <= current_time)
    ].copy()

    if waiting.empty:
        return state, None

    role_required = waiting.iloc[0]["role_required"]

    available_staff = staff[
        (staff["role"] == role_required) &
        (staff["status"] == "available")
    ]

    if available_staff.empty:
        return state, None

    # Pick first patient
    patient = waiting.sort_values(["priority", "entered_at"], ascending=[False, True]).iloc[0]
    staff_member = available_staff.iloc[0]

    task_end = current_time + pd.Timedelta(minutes=service_minutes)

    # Update queue
    state["current_queue_state"].loc[
        state["current_queue_state"]["queue_id"] == patient["queue_id"],
        "status"
    ] = "completed"

    # Update staff
    state["current_staff_status"].loc[
        state["current_staff_status"]["staff_id"] == staff_member["staff_id"],
        ["status", "busy_until"]
    ] = ["busy", task_end]

    task = {
        "encounter_id": patient["encounter_id"],
        "patient_id": patient["patient_id"],
        "task_start": current_time,
        "task_end": task_end,
        "staff_id": staff_member["staff_id"]
    }

    state = log_live_event(
        state,
        current_time,
        "task_started",
        encounter_id=task["encounter_id"],
        patient_id=task["patient_id"],
        staff_id=staff_member["staff_id"],
        details=f"{queue_type} started"
    )

    return state, task


def assign_bed_live(
    state,
    encounter_id,
    patient_id,
    unit_id,
    request_time,
    expected_los_hours=8,
    boarding_unit="U_ED"
):
    request_time = pd.Timestamp(request_time)

    beds_live = state["current_bed_status"]

    available = beds_live[
        (beds_live["unit_id"] == unit_id) &
        (beds_live["status"] == "available")
    ].copy()

    # Target bed available
    if not available.empty:
        bed = available.sort_values("bed_id").iloc[0]
        bed_id = bed["bed_id"]

        clinically_ready_time = request_time + pd.to_timedelta(expected_los_hours, unit="h")
        discharge_delay_hours = np.random.uniform(2, 12)
        expected_release_time = clinically_ready_time + pd.to_timedelta(discharge_delay_hours, unit="h")

        state["current_bed_status"].loc[
            state["current_bed_status"]["bed_id"] == bed_id,
            ["status", "encounter_id", "patient_id", "occupied_since", "expected_release_time"]
        ] = ["occupied", encounter_id, patient_id, request_time, expected_release_time]

        state["current_bed_status"].loc[
            state["current_bed_status"]["bed_id"] == bed_id,
            "clinically_ready_time"
        ] = clinically_ready_time

        state["current_patients"].loc[
            state["current_patients"]["encounter_id"] == encounter_id,
            ["current_unit", "current_status", "assigned_bed_id", "target_unit", "boarding_flag", "last_event_time"]
        ] = [unit_id, "in_bed", bed_id, unit_id, 0, request_time]

        state = log_live_event(
            state,
            request_time,
            "bed_assigned",
            encounter_id=encounter_id,
            patient_id=patient_id,
            unit_id=unit_id,
            bed_id=bed_id,
            details=f"Target bed assigned until {expected_release_time}"
        )

        return state, bed_id

    # Target unavailable, try ED boarding
    boarding_available = beds_live[
        (beds_live["unit_id"] == boarding_unit) &
        (beds_live["status"] == "available")
    ].copy()

    if unit_id in ["U_MED", "U_ICU", "U_SURG"] and not boarding_available.empty:
        bed = boarding_available.sort_values("bed_id").iloc[0]
        bed_id = bed["bed_id"]

        boarding_expected_release = request_time + pd.to_timedelta(24, unit="h")

        state["current_bed_status"].loc[
            state["current_bed_status"]["bed_id"] == bed_id,
            ["status", "encounter_id", "patient_id", "occupied_since", "expected_release_time"]
        ] = ["occupied", encounter_id, patient_id, request_time, boarding_expected_release]

        state["current_bed_status"].loc[
            state["current_bed_status"]["bed_id"] == bed_id,
            "clinically_ready_time"
        ] = pd.NaT

        state["current_patients"].loc[
            state["current_patients"]["encounter_id"] == encounter_id,
            ["current_unit", "current_status", "assigned_bed_id", "target_unit", "boarding_flag", "last_event_time"]
        ] = [boarding_unit, "boarding_in_ed", bed_id, unit_id, 1, request_time]

        queue_id = f"Q_BED_{encounter_id}_{unit_id}"

        exists = (
            (state["current_queue_state"]["queue_id"] == queue_id).any()
            if not state["current_queue_state"].empty and "queue_id" in state["current_queue_state"].columns
            else False
        )

        if not exists:
            queue_row = pd.DataFrame([{
                "queue_id": queue_id,
                "encounter_id": encounter_id,
                "patient_id": patient_id,
                "queue_type": "bed_queue",
                "unit_id": unit_id,
                "role_required": "bed_manager",
                "entered_at": request_time,
                "priority": 4,
                "status": "waiting"
            }])

            state["current_queue_state"] = pd.concat(
                [state["current_queue_state"], queue_row],
                ignore_index=True
            )

        state = log_live_event(
            state,
            request_time,
            "ed_boarding_started",
            encounter_id=encounter_id,
            patient_id=patient_id,
            unit_id=boarding_unit,
            bed_id=bed_id,
            details=f"No {unit_id} bed available. Patient boarding in ED."
        )

        return state, bed_id

    # No target bed and no boarding bed
    queue_id = f"Q_BED_{encounter_id}_{unit_id}"

    exists = (
        (state["current_queue_state"]["queue_id"] == queue_id).any()
        if not state["current_queue_state"].empty and "queue_id" in state["current_queue_state"].columns
        else False
    )

    if not exists:
        queue_row = pd.DataFrame([{
            "queue_id": queue_id,
            "encounter_id": encounter_id,
            "patient_id": patient_id,
            "queue_type": "bed_queue",
            "unit_id": unit_id,
            "role_required": "bed_manager",
            "entered_at": request_time,
            "priority": 4 if unit_id in ["U_ICU", "U_MED"] else 3,
            "status": "waiting"
        }])

        state["current_queue_state"] = pd.concat(
            [state["current_queue_state"], queue_row],
            ignore_index=True
        )

    state["current_patients"].loc[
        state["current_patients"]["encounter_id"] == encounter_id,
        ["current_status", "target_unit", "boarding_flag", "last_event_time"]
    ] = ["waiting_bed", unit_id, 0, request_time]

    state = log_live_event(
        state,
        request_time,
        "bed_request_waiting",
        encounter_id=encounter_id,
        patient_id=patient_id,
        unit_id=unit_id,
        details=f"No {unit_id} bed and no ED boarding bed available"
    )

    return state, None


def discharge_patient(state, encounter_id, discharge_time):
    discharge_time = pd.Timestamp(discharge_time)

    patients = state["current_patients"]

    patient_match = patients[
        patients["encounter_id"] == encounter_id
    ]

    if patient_match.empty:
        return state

    patient = patient_match.iloc[0]
    patient_id = patient.get("patient_id", None)
    bed_id = patient.get("assigned_bed_id", None)
    unit_id = patient.get("current_unit", patient.get("unit_id", None))

    # Release assigned bed if patient has one
    if pd.notna(bed_id) and "bed_id" in state["current_bed_status"].columns:
        bed_cols = state["current_bed_status"].columns

        reset_values = {}

        if "status" in bed_cols:
            reset_values["status"] = "available"
        if "encounter_id" in bed_cols:
            reset_values["encounter_id"] = None
        if "patient_id" in bed_cols:
            reset_values["patient_id"] = None
        if "occupied_since" in bed_cols:
            reset_values["occupied_since"] = pd.NaT
        if "expected_release_time" in bed_cols:
            reset_values["expected_release_time"] = pd.NaT
        if "clinically_ready_time" in bed_cols:
            reset_values["clinically_ready_time"] = pd.NaT

        for col, val in reset_values.items():
            state["current_bed_status"].loc[
                state["current_bed_status"]["bed_id"] == bed_id,
                col
            ] = val

    # Mark patient discharged
    patient_update_cols = state["current_patients"].columns

    if "current_status" in patient_update_cols:
        state["current_patients"].loc[
            state["current_patients"]["encounter_id"] == encounter_id,
            "current_status"
        ] = "discharged"

    if "last_event_time" in patient_update_cols:
        state["current_patients"].loc[
            state["current_patients"]["encounter_id"] == encounter_id,
            "last_event_time"
        ] = discharge_time

    # Close any waiting queues for this encounter
    if not state["current_queue_state"].empty and "encounter_id" in state["current_queue_state"].columns:
        state["current_queue_state"].loc[
            (state["current_queue_state"]["encounter_id"] == encounter_id) &
            (state["current_queue_state"]["status"] == "waiting"),
            "status"
        ] = "cancelled_after_discharge"

    state = log_live_event(
        state,
        discharge_time,
        "discharge",
        encounter_id=encounter_id,
        patient_id=patient_id,
        unit_id=unit_id,
        bed_id=bed_id,
        details="Patient discharged and bed released"
    )

    return state