# hospital_twin/kpi_engine.py

import pandas as pd

def compute_live_kpis(state, current_time=None):
    if current_time is None:
        current_time = state["clock"]

    current_time = pd.Timestamp(current_time)

    beds_live = state["current_bed_status"]
    patients = state["current_patients"]
    queue = state["current_queue_state"]
    staff = state["current_staff_status"]

    bed_kpi = (
        beds_live.groupby("unit_id")
        .agg(
            beds_total=("bed_id", "count"),
            beds_occupied=("status", lambda x: (x == "occupied").sum())
        )
        .reset_index()
    )

    bed_kpi["occupancy_rate"] = bed_kpi["beds_occupied"] / bed_kpi["beds_total"]

    if not queue.empty:
        queue_kpi = (
            queue[queue["status"] == "waiting"]
            .groupby(["unit_id", "queue_type"])
            .size()
            .reset_index(name="waiting_count")
        )
    else:
        queue_kpi = pd.DataFrame(columns=["unit_id", "queue_type", "waiting_count"])

    if not staff.empty:
        staff_kpi = (
            staff.groupby(["unit_id", "role", "status"])
            .size()
            .reset_index(name="staff_count")
        )
    else:
        staff_kpi = pd.DataFrame(columns=["unit_id", "role", "status", "staff_count"])

    system_kpi = pd.DataFrame([{
        "current_time": current_time,
        "active_patients": int((patients["current_status"] != "discharged").sum()) if not patients.empty else 0,
        "waiting_patients": int((queue["status"] == "waiting").sum()) if not queue.empty else 0,
        "occupied_beds": int((beds_live["status"] == "occupied").sum()) if not beds_live.empty else 0,
        "busy_staff": int((staff["status"] == "busy").sum()) if not staff.empty else 0,
        "ed_boarders": int((patients["current_status"] == "boarding_in_ed").sum()) if not patients.empty else 0
    }])

    return {
        "system_kpi": system_kpi,
        "bed_kpi": bed_kpi,
        "queue_kpi": queue_kpi,
        "staff_kpi": staff_kpi
    }