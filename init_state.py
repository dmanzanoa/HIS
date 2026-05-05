import pandas as pd

from live_state import initialize_live_state
from database import save_state

# Load static/config tables
beds = pd.read_csv("/home/mzo/digital_twin/data/beds.csv")
staff_shift_assignments = pd.read_csv("data/staff_shift_assignments.csv")

# Create live state from static config
state = initialize_live_state(
    beds=beds,
    staff_shift_assignments=staff_shift_assignments
)

# Save current_* live tables
save_state(state)

print("Live hospital state initialized successfully.")