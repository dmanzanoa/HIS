# hospital_twin/database.py

import os
import pandas as pd

STATE_DIR = "hospital_twin/live_state"

def save_state(state, state_dir=STATE_DIR):
    os.makedirs(state_dir, exist_ok=True)

    for key, value in state.items():
        if isinstance(value, pd.DataFrame):
            value.to_csv(f"{state_dir}/{key}.csv", index=False)

    with open(f"{state_dir}/clock.txt", "w") as f:
        f.write(str(state["clock"]))


def load_state(state_dir=STATE_DIR):
    state = {}

    for name in [
        "current_bed_status",
        "current_staff_status",
        "current_patients",
        "current_queue_state",
        "live_event_log"
    ]:
        path = f"{state_dir}/{name}.csv"
        if os.path.exists(path):
            state[name] = pd.read_csv(path)
        else:
            state[name] = pd.DataFrame()

    clock_path = f"{state_dir}/clock.txt"
    if os.path.exists(clock_path):
        with open(clock_path, "r") as f:
            state["clock"] = pd.Timestamp(f.read())
    else:
        state["clock"] = pd.Timestamp.now().floor("min")

    return state