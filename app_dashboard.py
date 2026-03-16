import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import os
import re

# 1. Page Config
st.set_page_config(page_title="Mtrol Precision Analytics", layout="wide")

# --- SMART FILE & STANDARD LOOKUP ---
def get_mtrol_standards(device_name, parameter_name):
    """
    Automatically finds the standard reference CSVs in the GitHub repo 
    and matches the selected parameter.
    """
    all_files = os.listdir('.')
    std_files = [f for f in all_files if "standard" in f.lower() and "values" in f.lower() and f.endswith(".csv")]
    
    # Identify if we need Mtrol 3 or 4 standards
    target_keyword = "Mtrol 3" if "3" in device_name else "Mtrol 4"
    target_file = next((f for f in std_files if target_keyword.lower() in f.lower()), None)
    
    # Fallback to any available standard file
    if not target_file and std_files:
        target_file = std_files[0]

    if target_file:
        try:
            std_df = pd.read_csv(target_file)
            # Normalize names: remove symbols, spaces, and units for matching
            def normalize(s): return re.sub(r'[^a-z0-9%]', '', str(s).lower())
            
            search_key = normalize(parameter_name.split(' ')[0])
            for idx, row in std_df.iterrows():
                if search_key in normalize(row['Parameters']):
                    return float(row['Minimum Value']), float(row['Maximum Value'])
        except Exception:
            pass
    return None, None

# --- AGGRESSIVE DATA CLEANING ---
@st.cache_data
def load_and_clean_data(file):
    df = pd.read_csv(file)
    
    # 1. Handle Time
    time_col = next((c for c in df.columns if "time" in c.lower()), None)
    if time_col:
        df[time_col] = pd.to_datetime(df[time_col], errors='coerce')
        df = df.sort_values(by=time_col).dropna(subset=[time_col])
    
    # 2. Clean numeric columns (removes '%', ',', and spaces)
    targets = ["flow", "opening", "p1", "p2", "temp", "chamber"]
    for col in df.columns:
        if col != time_col and any(t in col.lower() for t in targets):
            # Regex removes anything that isn't a digit, dot, or minus sign
            df[col] = pd.to_numeric(df[col].astype(str).str.replace(r'[^\d\.\-]', '', regex=True), errors='coerce')
    
    return df, time_col

# --- HEADER ---
st.title("Mtrol Precision Analytics")
st.caption("Standardized PPM Stability Dashboard | Dual-Axis Temperature Correlation")

# --- SIDEBAR & SYSTEM HEALTH ---
st.sidebar.header("📂 Data Source")
uploaded_file = st.sidebar.file_uploader("Upload Mtrol Dataset (CSV)", type=["csv"])

# Check if Standard CSVs exist in the GitHub Repo
all_files = os.listdir('.')
has_std3 = any("mtrol 3" in f.lower() and "standard" in f.lower() for f in all_files)
has_std4 = any("mtrol 4" in f.lower() and "standard" in f.lower() for f in all_files)

st.sidebar.markdown("---")
st.sidebar.subheader("Reference Standards Status")
st.sidebar.write(f"{'✅' if has_std3 else '❌'} Mtrol 3 Standards")
st.sidebar.write(f"{'✅' if has_std4 else '❌'} Mtrol 4 Standards")

if uploaded_file is not None:
    df, time_col = load_and_clean_data(uploaded_file)
    cols = df.columns.tolist()
    
    # Identify key columns in the uploaded file
    # We look for 'chamber' + 'temp' for the temperature axis
    temp_col = next((c for c in cols if "chamber" in c.lower() and "temp" in c.lower()), None)
    # Filter for P1, P2, Flow, and Opening
    available_params = [c for c in cols if any(t.lower() in c.lower() for t in ["flow", "opening", "p1", "p2"])]
    
    # Device Mode Detection
    device_name = "Mtrol 4" if "MT4" in uploaded_file.name.upper() else "Mtrol 3"
    st.sidebar.success(f"Mode: {device_name}")

    if not available_params:
        st.error("❌ No valid Mtrol parameters (P1, P2, Flow, Opening) found in CSV.")
    elif not temp_col:
        st.error("❌ 'Chamber Temperature' column not found. Please check your CSV column headers.")
    else:
        plot_col = st.sidebar.selectbox("Select Parameter to Analyze", available_params)
        
        # --- CALCULATION ENGINE ---
        std_min, std_max = get_mtrol_standards(device_name, plot_col)

        if std_min is not None and std_max is not None:
            # Clean up rows with missing values
            valid_df = df[[time_col, plot_col, temp_col]].dropna().copy()
            
            # 1. Get Expanding (Cumulative) Max and Min
            # This ensures the line is a steady "Stability" trend rather than noisy spikes
            in_max, in_min = valid_df[plot_col].expanding().max(), valid_df[plot_col].expanding().min()
            t_max, t_min = valid_df[temp_col].expanding().max(), valid_df[temp_col].expanding().min()
            
            # 2. Apply Formula: PPM = (ΔInput * 1,000,000) / (ΔTemp * ΔRef_Standard)
            std_range = std_max - std_min
            t_delta = (t_max - t_min)
            in_delta = (in_max - in_min)
            
            valid_df['Stability_PPM'] = (in_delta * 1000000) / (t_delta * std_range)
            
            # Clean up infinity errors at the very start of the cycle
            valid_df['Stability_PPM'] = valid_df['Stability_PPM'].replace([float('inf'), -float('inf')], 0).fillna(0)

            # --- DUAL AXIS PLOT ---
            fig = make_subplots(specs=[[{"secondary_y": True}]])

            # Left Axis: PPM Stability
            fig.add_trace(
                go.Scattergl(
                    x=valid_df[time_col], y=valid_df['Stability_PPM'], 
                    name="Stability Index (PPM)", 
                    line=dict(color="#00CCFF", width=2.5)
                ),
                secondary_y=False,
            )

            # Right Axis: Chamber Temperature
            fig.add_trace(
                go.Scattergl(
                    x=valid_df[time_col], y=valid_df[temp_col], 
                    name="Chamber Temp (°C)", 
                    line=dict(color="#00FF99", width=1, dash='dot')
                ),
                secondary_y=True,
            )

            fig.update_layout(
                template="plotly_dark", height=650,
                title=f"<b>Cycle Stability Trend: {plot_col} vs Temperature</b>",
                xaxis=dict(title="Cycle Timeline", rangeslider=dict(visible=True, thickness=0.05)),
                yaxis=dict(title="PPM Stability Index (Lower is Better)", gridcolor="#333"),
                yaxis2=dict(title="Temperature (°C)", side='right', gridcolor="#111"),
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
            )
            st.plotly_chart(fig, use_container_width=True)

            # --- SUMMARY METRICS ---
            m1, m2, m3 = st.columns(3)
            m1.metric("Final Cycle PPM", f"{valid_df['Stability_PPM'].iloc[-1]:.2f}")
            m2.metric(f"Avg {plot_col}", f"{valid_df[plot_col].mean():.4f}")
            m3.info(f"Ref Standards: {std_min} to {std_max}")
            
            # --- DATA TABLE ---
            st.markdown("### 📋 Cycle Data Points")
            df_display = valid_df.copy()
            df_display.insert(0, 'S.No.', range(1, len(df_display) + 1))
            st.dataframe(df_display.head(5000), use_container_width=True, hide_index=True)
        else:
            st.error(f"❌ Could not link '{plot_col}' to the Standard Reference CSV. Check that the parameter name in the standard file matches.")
