# 🏥 Hospital Information System + Digital Twin

This project simulates a real-time hospital operation system combining:

- Patient flow (arrival → triage → doctor → bed → discharge)
- Resource allocation (beds, staff)
- Event-driven simulation
- Live KPIs dashboard (Streamlit)

## Features

- Real-time patient pathway simulation
- Staff assignment engine
- Bed allocation + ED boarding logic
- Queue management (triage, physician, bed)
- Live KPI monitoring

## Tech Stack

- Python
- Pandas
- Streamlit

## Run

```bash
python init_state.py
streamlit run app.py
