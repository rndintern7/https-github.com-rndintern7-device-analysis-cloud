import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import os

# 1. Page Config
st.set_page_config(page_title="Mtrol Precision Analytics", layout="wide")

# --- Improved Function to fetch Standard Values ---
def get_mtrol_standards(device_name, parameter_name):
    file_map = {
        "Mtrol 3": "Standard Values 11-13 March - For Mtrol 3 Input.csv",
        "Mtrol 4": "Standard Values 11-13 March - For Mtrol 4 Input.csv"
    }
    try:
        if device_name in file_map and os.path.exists(file_map[device_name]):
            std_df = pd.read_csv(file_map[device_name])
            # Search for the parameter (e.g., search for "P1" in "P1 (bar)")
            # We take the first part of the parameter name to find the match
            search_key = parameter_name.split(' ')[0].split('(')[0].strip()
            match = std_df[std_df['Parameters'].str.contains(search_key, case=False, na=False)]
            
            if not match.empty:
                return float(match.iloc[0]['Minimum Value']), float(match.iloc[0]['Maximum Value'])
    except Exception as e:
        st.error(f"Error reading standards for {parameter_name}: {e}")
    return None, None

# --- Cached Data Loading with Numeric Cleaning ---
@st.cache_data
def load_and_clean_data(file):
    df = pd.read_csv(file)
    # Identify time column
    time_col = next((c for c in df.columns if "time" in c.lower()), None)
    if time_col:
        df[time_col] = pd.to_datetime(df[time_col], errors='coerce')
        df = df.sort_values(by=time_col).dropna(subset=[time_col])
    
    # Try to convert all columns to numeric where possible (cleaning strings/commas)
    for col in df.columns:
        if col != time_col:
            df[col] = pd.to_numeric(df[col].astype(str).str.replace(',', ''), errors='ignore')
    
    return df, time_col

# --- HEADER ---
st.title("Mtrol Precision Analytics")
st.caption("Robust Cumulative Stability Engine")

# --- DATA SOURCE ---
st.sidebar.header("📂 Data Source")
uploaded_file = st.sidebar.file_uploader("Upload Mtrol Dataset (CSV)", type=["csv"])

if uploaded_file is not None:
    df, time_col = load_and_clean_data(uploaded_file)
    cols = df.columns.tolist()
    
    # Define Targets
    mtrol_targets = ["Flow Rate", "% Opening", "P1", "P2"]
    temp_target_name = "Chamber Temperature" # Partial match
    
    # Identify Temperature Column
    actual_temp_col = next((c for c in cols if temp_target_name.lower() in c.lower()), None)
    
    # Identify Mtrol Parameters in the file
    available_mtrol_cols = []
    for target in mtrol_targets:
        match = [c for c in cols if target.lower() in c.lower()]
        available_mtrol_cols.extend(match)
    
    # Device Identification
    device_name = "Mtrol 4" if "MT4" in uploaded_file.name.upper() else "Mtrol 3"
    st.sidebar.success(f"Detected: {device_name}")

    if not available_mtrol_cols:
        st.error("❌ No Mtrol parameters (Flow, % Opening, P1, P2) found in CSV.")
    else:
        plot_col = st.sidebar.selectbox("Select Parameter", available_mtrol_cols)

        if actual_temp_col and pd.api.types.is_numeric_dtype(df[plot_col]):
            std_min, std_max = get_mtrol_standards(device_name, plot_col)

            if std_min is not None and std_max is not None:
                std_range = std_max - std_min
                
                # --- CUMULATIVE FORMULA CALCULATION ---
                # Expanding range for Max/Min inputs
                exp_input_max = df[plot_col].expanding().max()
                exp_input_min = df[plot_col].expanding().min()
                exp_temp_max = df[actual_temp_col].expanding().max()
                exp_temp_min = df[actual_temp_col].expanding().min()
                
                input_delta = exp_input_max - exp_input_min
                temp_delta = exp_temp_max - exp_temp_min
                
                # Calculation (PPM = (ΔInput * 1M) / (ΔTemp * ΔStd))
                # Prevent division by zero
                df['Cumulative_PPM'] = (input_delta * 1000000) / (temp_delta * std_range)
                df['Cumulative_PPM'] = df['Cumulative_PPM'].replace([float('inf'), -float('inf')], 0).fillna(0)

                final_ppm = df['Cumulative_PPM'].iloc[-1]

                # --- PLOT ---
                fig = make_subplots(specs=[[{"secondary_y": True}]])
                fig.add_trace(go.Scattergl(x=df[time_col], y=df['Cumulative_PPM'], 
                                         name="Stability Index (PPM)", line=dict(color="#00CCFF", width=2.5)), secondary_y=False)
                fig.add_trace(go.Scattergl(x=df[time_col], y=df[actual_temp_col], 
                                         name="Temp (°C)", line=dict(color="#00FF99", width=1, dash='dot')), secondary_y=True)

                fig.update_layout(template="plotly_dark", height=600,
                                title=f"<b>{plot_col} Stability Analysis</b>",
                                xaxis=dict(rangeslider=dict(visible=True, thickness=0.05)),
                                yaxis=dict(title="PPM Stability Index"),
                                yaxis2=dict(title="Temperature (°C)", overlaying='y', side='right'))
                st.plotly_chart(fig, use_container_width=True)

                # --- METRICS ---
                m1, m2, m3 = st.columns(3)
                m1.metric("Final Stability PPM", f"{final_ppm:.2f}")
                m2.metric(f"Avg {plot_col}", f"{df[plot_col].mean():.4f}")
                m3.info(f"Using Standards: {std_min} to {std_max}")
                
                st.markdown("### 📋 Filtered Data Preview")
                df_display = df.copy()
                df_display.insert(0, 'S.No.', range(1, len(df_display) + 1))
                st.dataframe(df_display.head(1000), use_container_width=True, hide_index=True)
            else:
                st.error(f"❌ Could not find Standard Values for '{plot_col}' in reference files.")
        else:
            if not actual_temp_col:
                st.error("❌ 'Chamber Temperature' column missing from data.")
            if not pd.api.types.is_numeric_dtype(df[plot_col]):
                st.error(f"❌ Parameter '{plot_col}' contains non-numeric data.")
