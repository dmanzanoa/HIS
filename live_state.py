import pandas as pd

def initialize_live_state(beds, staff_shift_assignments):

    # -------------------------------------------------
    # BEDS → LIVE STATUS
    # -------------------------------------------------
    beds_live = beds.copy()

    beds_live["status"] = "available"          # available / occupied / unavailable
    beds_live["occupied_by"] = None            # encounter_id
    beds_live["expected_release_time"] = pd.NaT

    # IMPORTANT: ensure required columns exist
    if "unit_id" not in beds_live.columns:
        raise ValueError("beds must contain 'unit_id' column")

    # -------------------------------------------------
    # STAFF → LIVE STATUS
    # -------------------------------------------------
    staff_live = staff_shift_assignments.copy()

    staff_live["status"] = "available"
    staff_live["busy_until"] = pd.NaT

    # -------------------------------------------------
    # EMPTY TABLES
    # -------------------------------------------------
    current_patients = pd.DataFrame(columns=[
        "encounter_id",
        "patient_id",
        "current_status",
        "unit_id",
        "priority",
        "arrival_time",
        "last_event_time"
    ])

    current_queue_state = pd.DataFrame(columns=[
        "queue_id",
        "encounter_id",
        "patient_id",
        "queue_type",
        "unit_id",
        "role_required",
        "entered_at",
        "priority",
        "status"
    ])

    live_event_log = pd.DataFrame(columns=[
        "event_time",
        "event_type",
        "encounter_id",
        "patient_id",
        "unit_id",
        "staff_id",
        "bed_id",
        "details"
    ])

    # -------------------------------------------------
    # FINAL STATE
    # -------------------------------------------------
    state = {
        "current_patients": current_patients,
        "current_bed_status": beds_live,
        "current_staff_status": staff_live,
        "current_queue_state": current_queue_state,
        "live_event_log": live_event_log,
        "clock": pd.Timestamp.now().floor("min")
    }

    return state