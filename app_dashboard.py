import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import os

# 1. Page Config
st.set_page_config(page_title="Mtrol Precision Analytics", layout="wide")

# --- Function to fetch Standard Values ---
def get_mtrol_standards(device_name, parameter_name):
    file_map = {
        "Mtrol 3": "Standard Values 11-13 March - For Mtrol 3 Input.csv",
        "Mtrol 4": "Standard Values 11-13 March - For Mtrol 4 Input.csv"
    }
    try:
        if device_name in file_map and os.path.exists(file_map[device_name]):
            std_df = pd.read_csv(file_map[device_name])
            # Match parameter (e.g., "P1" matches "P1 (bar)")
            match = std_df[std_df['Parameters'].str.contains(parameter_name.split(' ')[0], case=False)]
            if not match.empty:
                return float(match.iloc[0]['Minimum Value']), float(match.iloc[0]['Maximum Value'])
    except Exception:
        pass
    return None, None

# --- Cached Data Loading ---
@st.cache_data
def load_and_clean_data(file):
    df = pd.read_csv(file)
    time_col = next((c for c in df.columns if "time" in c.lower()), None)
    if time_col:
        df[time_col] = pd.to_datetime(df[time_col], errors='coerce')
        df = df.sort_values(by=time_col).dropna(subset=[time_col])
    return df, time_col

# --- HEADER ---
st.title("Mtrol Full-Cycle Stability Analysis")
st.caption("Cumulative PPM Stability Engine (Standardized)")

# --- DATA SOURCE ---
st.sidebar.header("📂 Data Source")
uploaded_file = st.sidebar.file_uploader("Upload Mtrol Dataset (CSV)", type=["csv"])

if uploaded_file is not None:
    df, time_col = load_and_clean_data(uploaded_file)
    cols = df.columns.tolist()
    
    mtrol_params = ["Flow Rate", "% Opening", "P1", "P2"]
    temp_target = "Chamber Temperature (°C)"
    
    # Device Identification
    device_name = "Mtrol 4" if "MT4" in uploaded_file.name.upper() else "Mtrol 3"
    st.sidebar.success(f"Detected: {device_name}")

    plot_col = st.sidebar.selectbox("Select Parameter", [c for c in mtrol_params if c in cols])

    # No Temperature Slider - Full Cycle Analysis
    df_cycle = df.copy()

    if not df_cycle.empty and temp_target in cols:
        is_numeric = pd.api.types.is_numeric_dtype(df_cycle[plot_col])
        std_min, std_max = get_mtrol_standards(device_name, plot_col)

        if is_numeric and std_min is not None and std_max is not None:
            std_range = std_max - std_min
            
            # --- CUMULATIVE FORMULA CALCULATION ---
            # To get a "Straight Line" stability plot, we calculate the formula cumulatively
            # using expanding windows (from start to current point)
            
            # Calculate rolling/expanding max and min for both input and temperature
            exp_input_max = df_cycle[plot_col].expanding().max()
            exp_input_min = df_cycle[plot_col].expanding().min()
            exp_temp_max = df_cycle[temp_target].expanding().max()
            exp_temp_min = df_cycle[temp_target].expanding().min()
            
            input_delta = exp_input_max - exp_input_min
            temp_delta = exp_temp_max - exp_temp_min
            
            # Applying your specific formula:
            # PPM = ([MaxIn - MinIn] * 1,000,000) / ([MaxTemp - MinTemp] * [StdMax - StdMin])
            # We handle division by zero for the initial points where range is 0
            df_cycle['Cumulative_PPM'] = (input_delta * 1000000) / (temp_delta * std_range)
            df_cycle['Cumulative_PPM'] = df_cycle['Cumulative_PPM'].replace([float('inf'), -float('inf')], 0).fillna(0)

            # Final Formula Metric (Last value in the cycle)
            final_ppm = df_cycle['Cumulative_PPM'].iloc[-1]

            # --- PLOT ---
            fig = make_subplots(specs=[[{"secondary_y": True}]])

            # Trace 1: Cumulative Stability (Formula PPM)
            fig.add_trace(
                go.Scattergl(
                    x=df_cycle[time_col], y=df_cycle['Cumulative_PPM'], 
                    name="Stability Index (PPM)", 
                    line=dict(color="#00CCFF", width=2.5) # Solid blue line
                ),
                secondary_y=False,
            )

            # Trace 2: Chamber Temperature (Secondary Axis)
            fig.add_trace(
                go.Scattergl(
                    x=df_cycle[time_col], y=df_cycle[temp_target], 
                    name="Chamber Temp (°C)", 
                    line=dict(color="#00FF99", width=1, dash='dot') # Dotted green line
                ),
                secondary_y=True,
            )

            fig.update_layout(
                template="plotly_dark", height=600,
                title=f"<b>Full Cycle Stability: {plot_col} vs Temperature</b>",
                xaxis=dict(title="Cycle Timestamp", rangeslider=dict(visible=True, thickness=0.05)),
                yaxis=dict(title="Stability Index (Calculated PPM)", gridcolor="#333"),
                yaxis2=dict(title="Temperature (°C)", overlaying='y', side='right', gridcolor="#111"),
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
            )
            st.plotly_chart(fig, use_container_width=True)

            # --- METRICS ---
            st.markdown("### 📊 Cycle Summary Statistics")
            m1, m2, m3 = st.columns(3)
            m1.metric("Final Cycle PPM", f"{final_ppm:.2f}")
            m2.metric(f"Avg {plot_col}", f"{df_cycle[plot_col].mean():.4f}")
            m3.info(f"Ref Standards: {std_min} to {std_max}")

            # --- TABLE ---
            st.markdown("### 📋 Filtered Results")
            df_display = df_cycle.copy()
            df_display.insert(0, 'S.No.', range(1, len(df_display) + 1))
            st.dataframe(df_display.head(5000), use_container_width=True, hide_index=True)
        else:
            st.error("Could not find standard values or parameter is non-numeric.")
    else:
        st.warning("Upload data containing 'Chamber Temperature' to begin full cycle analysis.")
