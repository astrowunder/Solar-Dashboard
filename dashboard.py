# -*- coding: utf-8 -*-
import streamlit as st
import plotly.graph_objects as go
import json
from datetime import datetime, date
from pygoodwe import API
import os
import time

st.set_page_config(page_title="GoodWe Solar", layout="wide")

st.markdown("""
<style>
    .block-container { padding-top: 0.3rem !important; padding-bottom: 0.3rem !important; }
    .stTable { margin-left: 0 !important; text-align: left !important; max-width: 700px; }
</style>
""", unsafe_allow_html=True)
st.markdown("<br>")
st.title("Prairie Unitarian Solar Production")

HISTORY_FILE = "power_history.json"
RATE_PER_KWH = 0.1513
CO2_PER_KWH = 0.4

# ==================== CONNECT TO GOODWE (using secrets) ====================
gw = API(
    system_id=st.secrets.goodwe.system_id,
    account=st.secrets.goodwe.account,
    password=st.secrets.goodwe.password
)
)

# ==================== LOAD HISTORY ====================
def load_history():
    if "power_history" not in st.session_state:
        if os.path.exists(HISTORY_FILE):
            try:
                with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                st.session_state.power_history = data.get("history", [])
                st.session_state.last_date = date.fromisoformat(data.get("last_date", str(date.today())))
            except Exception:
                if os.path.exists(HISTORY_FILE):
                    os.remove(HISTORY_FILE)
                st.session_state.power_history = []
                st.session_state.last_date = date.today()
        else:
            st.session_state.power_history = []
            st.session_state.last_date = date.today()

    if date.today() != st.session_state.last_date:
        st.session_state.power_history = []
        st.session_state.last_date = date.today()

load_history()

# ==================== FETCH DATA ====================
def fetch_data():
    try:
        data = gw.getCurrentReadings()
        inv = data.get("inverter", [{}])[0] if isinstance(data.get("inverter"), list) else data.get("inverter", {})
        invert_full = inv.get("invert_full", {})

        pac = invert_full.get("pac")
        eday = invert_full.get("eday") or invert_full.get("all_eday")
        etotal = invert_full.get("etotal") or invert_full.get("output_etotal")

        if pac is not None:
            now_str = datetime.now().strftime("%H:%M")
            st.session_state.power_history.append((now_str, float(pac)))

            if len(st.session_state.power_history) > 500:
                st.session_state.power_history = st.session_state.power_history[-500:]

            # Save safely
            try:
                temp_file = HISTORY_FILE + ".tmp"
                with open(temp_file, "w", encoding="utf-8") as f:
                    json.dump({
                        "history": st.session_state.power_history,
                        "last_date": str(st.session_state.last_date)
                    }, f, indent=2)
                os.replace(temp_file, HISTORY_FILE)
            except:
                pass  # silent fail on save is acceptable here

        return pac, eday, etotal

    except:
        return None, None, None


pac, eday, etotal = fetch_data()

# Calculations
daily_money = round((eday or 0) * RATE_PER_KWH, 2)
lifetime_money = round((etotal or 0) * RATE_PER_KWH, 2)
daily_co2 = round((eday or 0) * CO2_PER_KWH, 1)
lifetime_co2 = round((etotal or 0) * CO2_PER_KWH, 1)

# Layout
g1, g2 = st.columns([1, 2])

with g1:
    st.subheader("Current Power")
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=pac or 0,
        title={"text": "Live Output (Watts)"},
        gauge={"axis": {"range": [0, 7700]}, "bar": {"color": "#00cc96"}}
    ))
    fig.update_layout(height=300)
    st.plotly_chart(fig)   # No use_container_width

with g2:
    st.subheader("Power Output Today")
    if st.session_state.power_history:
        times_str = [t for t, p in st.session_state.power_history]
        powers = [p for t, p in st.session_state.power_history]
        x_values = [int(h)*60 + int(m) for t in times_str for h, m in [t.split(':')]]

        fig2 = go.Figure()
        fig2.add_trace(go.Scatter(
            x=x_values, y=powers, mode="lines+markers",
            line=dict(color="#00cc96", width=3), marker=dict(size=4)
        ))

        fig2.update_layout(
            xaxis_title="Time of Day",
            yaxis_title="Power (Watts)",
            height=300,
            template="plotly_dark",
            xaxis=dict(
                tickmode="array",
                tickvals=[0,180,360,540,720,900,1080,1260,1440],
                ticktext=["00:00","03:00","06:00","09:00","12:00","15:00","18:00","21:00","24:00"],
                range=[0, 1440]
            ),
            yaxis=dict(range=[0, 8000]),
            margin=dict(l=40, r=30, t=20, b=30)
        )
        st.plotly_chart(fig2)   # No use_container_width
    else:
        st.info("Waiting for first reading...")

st.subheader("Summary")
data = {
    "Metric": ["Generated", "Money Saved", "CO₂ Saved"],
    "Today": [f"{eday:.1f} kWh" if eday is not None else "---", f"${daily_money}", f"{daily_co2} kg"],
    "Lifetime": [f"{etotal:.1f} kWh" if etotal is not None else "---", f"${lifetime_money}", f"{lifetime_co2} kg"]
}
st.table(data)

st.caption("Auto-refreshing every 15 seconds • Data from GoodWe SEMS")

# Auto refresh
time.sleep(15)
st.rerun()