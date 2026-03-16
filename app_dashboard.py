import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import base64
import os

# 1. Page Config
st.set_page_config(page_title="Mtrol Precision Analytics", layout="wide")

# --- Function to fetch Standard Values based on Device and Parameter ---
def get_mtrol_standards(device_name, parameter_name):
    # Mapping to your uploaded standard files
    file_map = {
        "Mtrol 3": "Standard Values 11-13 March - For Mtrol 3 Input.csv",
        "Mtrol 4": "Standard Values 11-13 March - For Mtrol 4 Input.csv"
    }
    
    try:
        if device_name in file_map and os.path.exists(file_map[device_name]):
            std_df = pd.read_csv(file_map[device_name])
            # Match parameter name (e.g., "P1" matches "P1 (bar)")
            match = std_df[std_df['Parameters'].str.contains(parameter_name.split(' ')[0], case=False)]
            if not match.empty:
                return float(match.iloc[0]['Minimum Value']), float(match.iloc[0]['Maximum Value'])
    except Exception as e:
        st.error(f"Error loading standards: {e}")
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
st.title("Mtrol Precision Analytics")
st.caption("Standardized PPM Formula Engine")

# --- DATA SOURCE ---
st.sidebar.header("📂 Data Source")
uploaded_file = st.sidebar.file_uploader("Upload Mtrol Dataset (CSV)", type=["csv"])

if uploaded_file is not None:
    df, time_col = load_and_clean_data(uploaded_file)
    cols = df.columns.tolist()
    
    # 14 Color Palette
    color_map = {
        "Flow Rate": "#FF4B4B", "% Opening": "#FF8F8F", 
        "P1": "#A64DFF", "P2": "#D9B3FF",
        "C1 Measurement": "#00CCFF", "C2 Measurement": "#33FFFF"
    }

    mtrol_params = ["Flow Rate", "% Opening", "P1", "P2"]
    temp_target = "Chamber Temperature (°C)"
    
    # Device Identification Logic
    device_name = "Mtrol 4" if "MT4" in uploaded_file.name.upper() else "Mtrol 3"
    st.sidebar.success(f"Mode: {device_name}")

    plot_col = st.sidebar.selectbox("Select Parameter", [c for c in mtrol_params if c in cols])

    # --- FILTERS ---
    st.sidebar.markdown("---")
    st.sidebar.subheader("🎯 Temperature Filter")
    df_filtered = df.copy()
    filter_text = "All Data"

    if temp_target in cols:
        target_temp = st.sidebar.slider("Target Temp (°C)", -40.0, 100.0, 70.0, 0.5)
        tol = st.sidebar.slider("Tolerance (+/- °C)", 0.1, 10.0, 1.0)
        df_filtered = df[(df[temp_target] >= target_temp - tol) & (df[temp_target] <= target_temp + tol)].copy()
        filter_text = f"Temp: {target_temp}°C | Tolerance: ±{tol}°C"

    if not df_filtered.empty:
        # --- DYNAMIC PPM CALCULATION ---
        is_numeric = pd.api.types.is_numeric_dtype(df_filtered[plot_col])
        param_avg = df_filtered[plot_col].mean() if is_numeric else 0
        
        formula_ppm = 0
        std_min, std_max = get_mtrol_standards(device_name, plot_col)

        if std_min is not None and std_max is not None and temp_target in cols:
            # 1. Input Min/Max from filtered data
            input_max = df_filtered[plot_col].max()
            input_min = df_filtered[plot_col].min()
            
            # 2. Chamber Temp Min/Max from filtered data
            temp_max = df_filtered[temp_target].max()
            temp_min = df_filtered[temp_target].min()
            
            temp_range = temp_max - temp_min
            std_range = std_max - std_min
            
            # 3. Applying your NEW formula:
            # PPM = ([Max Input - Min Input] * 1,000,000) / ([Max Temp - Min Temp] * [Std Max - Std Min])
            if temp_range != 0 and std_range != 0:
                formula_ppm = ((input_max - input_min) * 1000000) / (temp_range * std_range)

        # Graph Data (PPM Deviation from Average for trend view)
        if is_numeric and param_avg != 0:
            df_filtered['PPM_Dev'] = ((df_filtered[plot_col] - param_avg) / param_avg * 1_000_000)
            y_col = 'PPM_Dev'
        else:
            y_col = plot_col

        # --- PLOT ---
        fig = go.Figure()
        fig.add_trace(go.Scattergl(
            x=df_filtered[time_col], y=df_filtered[y_col], 
            mode='lines+markers', marker=dict(color=color_map.get(plot_col, "#FFFFFF"), size=4),
            line=dict(width=1.5), name=plot_col
        ))
        
        fig.update_layout(
            template="plotly_dark", height=550,
            annotations=[{
                "x": 1, "y": 1.1, "xref": "paper", "yref": "paper",
                "text": f"Device: {device_name} | Filter: {filter_text}",
                "showarrow": False, "bgcolor": "rgba(50,50,50,0.8)", "bordercolor": "#FF4B4B", "borderwidth": 1
            }]
        )
        st.plotly_chart(fig, use_container_width=True)

        # --- STATISTICS ---
        st.markdown("### 📊 Metrics Summary")
        m1, m2, m3 = st.columns(3)
        m1.metric(f"Avg {plot_col}", f"{param_avg:.4f}")
        m2.metric("New Formula PPM", f"{formula_ppm:.2f}")
        m3.info(f"Using Standard Range: {std_min} to {std_max}")

        # --- DATA TABLE WITH S.No. ---
        st.markdown("### 📋 Data Preview")
        df_display = df_filtered.copy()
        df_display.insert(0, 'S.No.', range(1, len(df_display) + 1))
        st.dataframe(df_display.head(1000), use_container_width=True, hide_index=True)
    else:
        st.warning("No data found for the selected temperature range.")
