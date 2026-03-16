import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import base64
import os

# 1. Page Config
st.set_page_config(page_title="Advanced Product Analytics", layout="wide")

# --- Function to load logo (Modified for Cloud Paths) ---
def get_base64_image(image_path):
    try:
        # Check if file exists to prevent cloud crash
        if os.path.exists(image_path):
            with open(image_path, "rb") as img_file:
                return base64.b64encode(img_file.read()).decode()
        return ""
    except: return ""

logo_base64 = get_base64_image("logo.png")

# --- HEADER ---
col_title, col_logo = st.columns([8, 2])
with col_title:
    st.title("Device Analysis System")

with col_logo:
    if logo_base64:
        st.markdown(f'<div style="text-align:right;"><img src="data:image/png;base64,{logo_base64}" style="width:180px;"></div>', unsafe_allow_html=True)

# 2. SIDEBAR CONFIGURATION
st.sidebar.header("📊 Control Panel")
device = st.sidebar.selectbox("Select Product", ["Mtrol 3", "Mtrol 4", "MUPT"])

# Define Parameters for each device
params_map = {
    "Mtrol 3": ["1: Flow Rate", "2: % Opening", "3: P1", "4: P2"],
    "Mtrol 4": ["1: Flow Rate", "2: % Opening", "3: P1", "4: P2"],
    "MUPT": ["C1 Measurement", "C2 Measurement", "T1 Measurement", "T2 Measurement", 
             "Trap Mode", "Bypass Mode", "Solenoid Status", "Steam Leak", 
             "Water Log/Process Off", "Cooling Cycle Switch"]
}

# --- COLOR PALETTE ---
color_palette = {
    "Mtrol 3": {"1: Flow Rate": "#1f77b4", "2: % Opening": "#2ca02c", "3: P1": "#ff7f0e", "4: P2": "#9467bd"},
    "Mtrol 4": {"1: Flow Rate": "#d62728", "2: % Opening": "#17becf", "3: P1": "#bcbd22", "4: P2": "#e377c2"},
    "MUPT": {
        "C1 Measurement": "#1f77b4", "C2 Measurement": "#ff7f0e", 
        "T1 Measurement": "#2ca02c", "T2 Measurement": "#d62728",
        "Trap Mode": "#9467bd", "Bypass Mode": "#8c564b", 
        "Solenoid Status": "#e377c2", "Steam Leak": "#7f7f7f",
        "Water Log/Process Off": "#bcbd22", "Cooling Cycle Switch": "#17becf"
    }
}

param_choice = st.sidebar.selectbox("Parameter to Visualize", params_map[device])

# 3. DATA CONFIGURATION & LOADING
# Ensure these filenames match exactly what you upload to GitHub
config = {
    "Mtrol 3": {"file": "Mtrol_3_11-13_March_2min_Average - Mtrol_3_11-13_March_2min_Average.csv.csv", "time": "Time Stamp", "temp": "Chamber Temperature (°C)"},
    "Mtrol 4": {"file": "Mtrol_4_11-13_March_2min_Average - Mtrol_4_11-13_March_2min_Average.csv.csv", "time": "Time Stamp", "temp": "Chamber Temperature (°C)"},
    "MUPT": {"file": "MUPT 1 - Sheet 1.csv", "time": "Timestamp"}
}

@st.cache_data
def load_data(dev):
    file_path = config[dev]["file"]
    if not os.path.exists(file_path):
        st.error(f"File not found: {file_path}. Please upload it to your GitHub repository.")
        return None
    df = pd.read_csv(file_path)
    df[config[dev]["time"]] = pd.to_datetime(df[config[dev]["time"]])
    return df

try:
    df = load_data(device)
    
    if df is not None:
        df_filtered = df.copy()

        # --- DYNAMIC FILTERS ---
        st.sidebar.markdown("---")
        st.sidebar.subheader("🎯 Data Filters")

        if device == "MUPT":
            mupt_filter_cols = ["C1 Measurement", "C2 Measurement", "T1 Measurement", "T2 Measurement"]
            for col in mupt_filter_cols:
                min_v, max_v = float(df[col].min()), float(df[col].max())
                r = st.sidebar.slider(f"Filter {col}", min_v, max_v, (min_v, max_v))
                df_filtered = df_filtered[(df_filtered[col] >= r[0]) & (df_filtered[col] <= r[1])]
        else:
            target_temp = st.sidebar.slider("Target Temperature (°C)", -20.0, 80.0, 70.0, 0.5)
            tol = st.sidebar.slider("Tolerance (+/- °C)", 0.1, 5.0, 1.0)
            t_col = config[device]["temp"]
            df_filtered = df_filtered[(df_filtered[t_col] >= target_temp - tol) & (df_filtered[t_col] <= target_temp + tol)]

        # --- COLUMN MAPPING ---
        if "Mtrol" in device:
            mapping = {'1: Flow Rate': 'Flow Rate', '2: % Opening': '% Opening', '3: P1': 'P1', '4: P2': 'P2'}
            plot_col = mapping[param_choice]
        else:
            plot_col = param_choice

        time_col = config[device]["time"]

        if not df_filtered.empty:
            # CALCULATIONS
            mean_val = df_filtered[plot_col].mean()
            df_filtered['PPM'] = ((df_filtered[plot_col] - mean_val) / mean_val * 1_000_000) if mean_val != 0 else 0

            # --- 4. GRAPH ---
            selected_color = color_palette[device][param_choice]
            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=df_filtered[time_col], 
                y=df_filtered['PPM'], 
                mode='lines+markers', 
                line=dict(color=selected_color, width=2),
                name=f"{device}: {param_choice}"
            ))
            
            fig.update_layout(
                title=f"<b>{device} Stability: {plot_col}</b>",
                xaxis=dict(title="Time Stamp", rangeslider=dict(visible=True)),
                yaxis=dict(title="PPM Deviation"),
                template="plotly_white",
                height=550,
                showlegend=True,
                legend=dict(orientation="v", yanchor="top", y=1, xanchor="left", x=1.02, bgcolor="rgba(255,255,255,0.8)", bordercolor="gray", borderwidth=1),
                margin=dict(r=150)
            )
            st.plotly_chart(fig, use_container_width=True)

            # --- 5. STATISTICS ---
            st.markdown("### 📊 Statistics Summary")
            c1, c2, c3 = st.columns(3)
            c1.metric("Mean Value", f"{mean_val:.4f}")
            c2.metric("Peak PPM", f"{df_filtered['PPM'].max():.2f}")
            c3.metric("Min PPM", f"{df_filtered['PPM'].min():.2f}")

            st.markdown("---") 
            
            # --- 6. DATA TABLE ---
            st.subheader("📋 Filtered Data Results")
            display_cols = [time_col, plot_col, 'PPM']
            if "Mtrol" in device: display_cols.insert(1, config[device]["temp"])
            st.dataframe(df_filtered[display_cols], use_container_width=True, hide_index=True)
        else:
            st.warning("No data found for the selected filter ranges.")

except Exception as e:
    st.error(f"Error: {e}")
