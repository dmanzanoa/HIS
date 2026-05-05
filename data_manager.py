import pandas as pd
from pathlib import Path

BASE = Path("hospital_twin/data")

def load_config_tables():
    return {
        "beds": pd.read_csv(BASE / "config/beds.csv"),
        "staff": pd.read_csv(BASE / "config/staff.csv"),
        "staff_shift_assignments": pd.read_csv(BASE / "config/staff_shift_assignments.csv"),
        "staff_shifts_planned": pd.read_csv(BASE / "config/staff_shifts_planned.csv")
    }

def load_simulation_tables():
    return {
        "encounter_features": pd.read_csv(BASE / "processed/encounter_features.csv"),
        "encounter_simulated_timeline": pd.read_csv(BASE / "processed/encounter_simulated_timeline.csv"),
        "bed_requests": pd.read_csv(BASE / "simulation/bed_requests.csv"),
        "bed_assignments": pd.read_csv(BASE / "simulation/bed_assignments.csv"),
        "patient_pathway_events": pd.read_csv(BASE / "simulation/patient_pathway_events.csv"),
        "queue_events": pd.read_csv(BASE / "simulation/queue_events.csv"),
        "staff_task_events": pd.read_csv(BASE / "simulation/staff_task_events.csv")
    }

def load_live_state():
    return {
        "current_patients": pd.read_csv(BASE / "live_state/current_patients.csv"),
        "current_bed_status": pd.read_csv(BASE / "live_state/current_bed_status.csv"),
        "current_staff_status": pd.read_csv(BASE / "live_state/current_staff_status.csv"),
        "current_queue_state": pd.read_csv(BASE / "live_state/current_queue_state.csv"),
        "live_event_log": pd.read_csv(BASE / "live_state/live_event_log.csv")
    }