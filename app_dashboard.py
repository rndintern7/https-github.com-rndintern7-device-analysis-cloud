import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import os
import re

# 1. Page Config
st.set_page_config(page_title="Mtrol Precision Analytics", layout="wide")

# --- SIDEBAR LOGO ---
if os.path.exists("logo.png"):
    st.sidebar.image("logo.png", use_container_width=True)
else:
    st.sidebar.title("Mtrol Analytics")

# --- SMART STANDARD LOOKUP ---
def get_mtrol_standards(device_name, parameter_name):
    # Mapping the files you uploaded to the device names
    file_map = {
        "Mtrol 3": "Standard Values 11-13 March - For Mtrol 3 Input.csv",
        "Mtrol 4": "Standard Values 11-13 March - For Mtrol 4 Input.csv"
    }
    
    filename = file_map.get(device_name)
    
    if filename and os.path.exists(filename):
        try:
            std_df = pd.read_csv(filename)
            # Use regex to find parameter (matches "P1" in "P1 (bar)")
            search_key = parameter_name.split(' ')[0].split('(')[0].strip()
            match = std_df[std_df['Parameters'].str.contains(search_key, case=False, na=False)]
            
            if not match.empty:
                return float(match.iloc[0]['Minimum Value']), float(match.iloc[0]['Maximum Value'])
        except Exception:
            pass
    return None, None

# --- DATA CLEANING ---
@st.cache_data
def load_and_clean_data(file):
    df = pd.read_csv(file)
    time_col = next((c for c in df.columns if "time" in c.lower()), None)
    if time_col:
        df[time_col] = pd.to_datetime(df[time_col], errors='coerce')
        df = df.sort_values(by=time_col).dropna(subset=[time_col])
    
    # Clean numeric data (removes %, commas, etc.)
    targets = ["flow", "opening", "p1", "p2", "temp", "chamber"]
    for col in df.columns:
        if col != time_col and any(t in col.lower() for t in targets):
            df[col] = pd.to_numeric(df[col].astype(str).str.replace(r'[^\d\.\-]', '', regex=True), errors='coerce')
    return df, time_col

# --- MAIN UI ---
st.title("Mtrol Full-Cycle Stability Dashboard")
st.caption("Standardized PPM Calculation Engine")

st.sidebar.header("📂 Data Source")
uploaded_file = st.sidebar.file_uploader("Upload Mtrol Dataset (CSV)", type=["csv"])

# System Health Check in Sidebar
st.sidebar.markdown("---")
st.sidebar.subheader("Reference Files Status")
st.sidebar.write(f"{'✅' if os.path.exists('Standard Values 11-13 March - For Mtrol 3 Input.csv') else '❌'} Mtrol 3 Standards")
st.sidebar.write(f"{'✅' if os.path.exists('Standard Values 11-13 March - For Mtrol 4 Input.csv') else '❌'} Mtrol 4 Standards")

if uploaded_file is not None:
    df, time_col = load_and_clean_data(uploaded_file)
    
    # Detection logic
    device_name = "Mtrol 4" if "MT4" in uploaded_file.name.upper() else "Mtrol 3"
    st.sidebar.success(f"Mode: {device_name}")

    # Column identification
    temp_col = next((c for c in df.columns if "chamber" in c.lower() and "temp" in c.lower()), None)
    params = [c for c in df.columns if any(t.lower() in c.lower() for t in ["flow", "opening", "p1", "p2"])]

    if params and temp_col:
        plot_col = st.sidebar.selectbox("Select Parameter", params)
        std_min, std_max = get_mtrol_standards(device_name, plot_col)

        if std_min is not None and std_max is not None:
            # Formula Logic: PPM = (ΔInput * 1M) / (ΔTemp * ΔStd)
            valid_df = df[[time_col, plot_col, temp_col]].dropna().copy()
            
            # Use expanding window to prevent spikes
            in_range = valid_df[plot_col].expanding().max() - valid_df[plot_col].expanding().min()
            temp_range = valid_df[temp_col].expanding().max() - valid_df[temp_col].expanding().min()
            std_range = std_max - std_min
            
            valid_df['PPM'] = (in_range * 1000000) / (temp_range * std_range)
            valid_df['PPM'] = valid_df['PPM'].replace([float('inf'), -float('inf')], 0).fillna(0)

            # Plotting
            fig = make_subplots(specs=[[{"secondary_y": True}]])
            fig.add_trace(go.Scattergl(x=valid_df[time_col], y=valid_df['PPM'], name="Stability Index (PPM)", line=dict(color="#00CCFF", width=2)), secondary_y=False)
            fig.add_trace(go.Scattergl(x=valid_df[time_col], y=valid_df[temp_col], name="Temp (°C)", line=dict(color="#00FF99", width=1, dash='dot')), secondary_y=True)

            fig.update_layout(template="plotly_dark", height=600, title=f"<b>Cycle Analysis: {plot_col}</b>",
                            xaxis=dict(rangeslider=dict(visible=True, thickness=0.05)),
                            yaxis=dict(title="Calculated PPM"), yaxis2=dict(title="Chamber Temp (°C)", side='right'))
            st.plotly_chart(fig, use_container_width=True)

            # Final Metric
            st.metric("Final Cycle PPM", f"{valid_df['PPM'].iloc[-1]:.2f}")
        else:
            st.error(f"Could not find standards for {plot_col} in the uploaded CSVs.")
    else:
        st.error("Missing Chamber Temperature or Mtrol parameters in uploaded data.")
