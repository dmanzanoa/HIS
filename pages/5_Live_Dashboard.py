import streamlit as st
import pandas as pd

from database import load_state
from kpi_engine import compute_live_kpis

st.title("📊 Live Hospital Dashboard")

state = load_state()
kpis = compute_live_kpis(state)

sys = kpis["system_kpi"].iloc[0]

c1, c2, c3, c4, c5 = st.columns(5)

c1.metric("Active Patients", int(sys["active_patients"]))
c2.metric("Waiting Patients", int(sys["waiting_patients"]))
c3.metric("Occupied Beds", int(sys["occupied_beds"]))
c4.metric("Busy Staff", int(sys["busy_staff"]))
c5.metric("ED Boarders", int(sys["ed_boarders"]))

st.subheader("Bed Occupancy")
st.dataframe(kpis["bed_kpi"], use_container_width=True)

if not kpis["bed_kpi"].empty:
    st.bar_chart(kpis["bed_kpi"].set_index("unit_id")["occupancy_rate"])

st.subheader("Queues")
st.dataframe(kpis["queue_kpi"], use_container_width=True)

st.subheader("Staff")
st.dataframe(kpis["staff_kpi"], use_container_width=True)

st.subheader("Current Patients")
st.dataframe(state["current_patients"], use_container_width=True)

st.subheader("Recent Events")
st.dataframe(state["live_event_log"].tail(100), use_container_width=True)