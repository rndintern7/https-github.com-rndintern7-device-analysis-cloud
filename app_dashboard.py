import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import os
import re

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
            # Use regex to find parameter (e.g., search for "P1" in "P1 (bar)")
            search_key = parameter_name.split(' ')[0].split('(')[0].strip()
            match = std_df[std_df['Parameters'].str.contains(search_key, case=False, na=False)]
            
            if not match.empty:
                return float(match.iloc[0]['Minimum Value']), float(match.iloc[0]['Maximum Value'])
    except Exception as e:
        st.error(f"Error reading standards for {parameter_name}: {e}")
    return None, None

# --- Advanced Numeric Cleaning Function ---
def clean_numeric_series(series):
    # 1. Convert to string and strip whitespace
    s = series.astype(str).str.strip()
    # 2. Remove percentage signs, commas, and other non-numeric chars (except dots and minus)
    s = s.str.replace(r'[^\d\.\-]', '', regex=True)
    # 3. Convert to numeric, turning failures into NaN
    return pd.to_numeric(s, errors='coerce')

# --- Cached Data Loading with Aggressive Cleaning ---
@st.cache_data
def load_and_clean_data(file):
    df = pd.read_csv(file)
    
    # Identify time column
    time_col = next((c for c in df.columns if "time" in c.lower()), None)
    if time_col:
        df[time_col] = pd.to_datetime(df[time_col], errors='coerce')
        df = df.sort_values(by=time_col).dropna(subset=[time_col])
    
    # Target columns to clean specifically
    targets = ["flow", "opening", "p1", "p2", "temperature", "temp"]
    
    for col in df.columns:
        if col != time_col:
            # If the column name matches our target keywords, force clean it
            if any(t in col.lower() for t in targets):
                df[col] = clean_numeric_series(df[col])
            else:
                # Try soft conversion for others
                df[col] = pd.to_numeric(df[col], errors='ignore')
    
    return df, time_col

# --- HEADER ---
st.title("Mtrol Precision Analytics")
st.caption("Robust Cumulative Stability Engine - Optimized for Dirty Data")

# --- DATA SOURCE ---
st.sidebar.header("📂 Data Source")
uploaded_file = st.sidebar.file_uploader("Upload Mtrol Dataset (CSV)", type=["csv"])

if uploaded_file is not None:
    df, time_col = load_and_clean_data(uploaded_file)
    cols = df.columns.tolist()
    
    mtrol_targets = ["Flow Rate", "% Opening", "P1", "P2"]
    temp_target_name = "Chamber Temperature"
    
    actual_temp_col = next((c for c in cols if temp_target_name.lower() in c.lower()), None)
    
    available_mtrol_cols = []
    for target in mtrol_targets:
        match = [c for c in cols if target.lower() in c.lower()]
        available_mtrol_cols.extend(match)
    
    device_name = "Mtrol 4" if "MT4" in uploaded_file.name.upper() else "Mtrol 3"
    st.sidebar.success(f"Detected: {device_name}")

    if not available_mtrol_cols:
        st.error("❌ No Mtrol parameters found. Check your CSV column names.")
    else:
        plot_col = st.sidebar.selectbox("Select Parameter", available_mtrol_cols)

        # Final check if data is numeric after cleaning
        if actual_temp_col and pd.api.types.is_numeric_dtype(df[plot_col]):
            std_min, std_max = get_mtrol_standards(device_name, plot_col)

            if std_min is not None and std_max is not None:
                std_range = std_max - std_min
                
                # Formula inputs
                # Using fillna(method='ffill') to handle any scattered NaNs from cleaning
                clean_param = df[plot_col].fillna(method='ffill')
                clean_temp = df[actual_temp_col].fillna(method='ffill')

                exp_input_max = clean_param.expanding().max()
                exp_input_min = clean_param.expanding().min()
                exp_temp_max = clean_temp.expanding().max()
                exp_temp_min = clean_temp.expanding().min()
                
                input_delta = exp_input_max - exp_input_min
                temp_delta = exp_temp_max - exp_temp_min
                
                # PPM = ([MaxIn - MinIn] * 1,000,000) / ([MaxTemp - MinTemp] * [StdMax - StdMin])
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
                                title=f"<b>{plot_col} Full Cycle Stability</b>",
                                xaxis=dict(rangeslider=dict(visible=True, thickness=0.05)),
                                yaxis=dict(title="PPM Stability Index"),
                                yaxis2=dict(title="Temperature (°C)", overlaying='y', side='right'))
                st.plotly_chart(fig, use_container_width=True)

                # --- METRICS ---
                m1, m2, m3 = st.columns(3)
                m1.metric("Final Cycle PPM", f"{final_ppm:.2f}")
                m2.metric(f"Avg {plot_col}", f"{clean_param.mean():.4f}")
                m3.info(f"Using Standards: {std_min} to {std_max}")
            else:
                st.error(f"❌ Standard values for '{plot_col}' not found.")
        else:
            if not actual_temp_col:
                st.error("❌ 'Chamber Temperature' column missing.")
            else:
                st.error(f"❌ '{plot_col}' is still non-numeric. Please check for text in data cells.")
