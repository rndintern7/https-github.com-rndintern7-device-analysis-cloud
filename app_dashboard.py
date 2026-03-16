import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import base64
import os

# 1. Page Config
st.set_page_config(page_title="Device Analysis System", layout="wide")

# --- Function to load logo ---
def get_base64_image(image_path):
    try:
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
    st.caption("Stability Analysis with Time-Series Graphing")

with col_logo:
    if logo_base64:
        st.markdown(f'<div style="text-align:right;"><img src="data:image/png;base64,{logo_base64}" style="width:180px;"></div>', unsafe_allow_html=True)

# --- 2. CLOUD DATA UPLOADER ---
st.sidebar.header("📂 Data Source")
uploaded_file = st.sidebar.file_uploader("Upload your Dataset (CSV)", type=["csv"])

if uploaded_file is not None:
    df = pd.read_csv(uploaded_file)
    cols = df.columns.tolist()
    
    # 3. COLOR CONFIGURATION
    color_map = {
        "C1 Measurement": "#1f77b4", "C2 Measurement": "#42a5f5",
        "T1 Measurement": "#2ca02c", "T2 Measurement": "#66bb6a",
        "Flow Rate": "#d62728", "% Opening": "#ef5350",
        "P1": "#ff7f0e", "P2": "#ffb74d"
    }

    # 4. PARAMETER & TIME DETECTION
    mupt_targets = ["C1 Measurement", "C2 Measurement", "T1 Measurement", "T2 Measurement"]
    mtrol_targets = ["Flow Rate", "% Opening", "P1", "P2"]
    temp_target = "Chamber Temperature (°C)"
    
    # Detect Time Column (Mtrol uses "Time Stamp", MUPT uses "Timestamp")
    time_col = next((c for c in cols if "time" in c.lower()), None)
    
    found_mupt = [p for p in mupt_targets if p in cols]
    found_mtrol = [p for p in mtrol_targets if p in cols]
    is_mtrol = len(found_mtrol) > 0

    st.sidebar.markdown("---")
    st.sidebar.header("⚙️ Analysis Settings")
    
    all_found = found_mupt + found_mtrol
    if not all_found:
        st.error("⚠️ No target parameters found in CSV.")
    else:
        plot_col = st.sidebar.selectbox("Select Parameter to Analyze", all_found)

        # 5. DYNAMIC FILTERS
        st.sidebar.markdown("---")
        st.sidebar.subheader("🎯 Data Filters")
        df_filtered = df.copy()

        if is_mtrol and temp_target in cols:
            target_temp = st.sidebar.slider("Target Chamber Temp (°C)", -40.0, 100.0, 70.0, 0.5)
            tol = st.sidebar.slider("Tolerance (+/- °C)", 0.1, 10.0, 1.0)
            df_filtered = df_filtered[
                (df_filtered[temp_target] >= target_temp - tol) & 
                (df_filtered[temp_target] <= target_temp + tol)
            ]
        elif not is_mtrol:
            for p in found_mupt:
                min_v, max_v = float(df[p].min()), float(df[p].max())
                r = st.sidebar.slider(f"Filter {p}", min_v, max_v, (min_v, max_v))
                df_filtered = df_filtered[(df_filtered[p] >= r[0]) & (df_filtered[p] <= r[1])]

        if not df_filtered.empty:
            # 6. TIME CONVERSION
            if time_col:
                df_filtered[time_col] = pd.to_datetime(df_filtered[time_col])
                x_axis_data = df_filtered[time_col]
                x_label = "Time Stamp"
            else:
                x_axis_data = list(range(1, len(df_filtered) + 1))
                x_label = "Sequence Index (Time column not found)"

            # CALCULATIONS
            mean_val = df_filtered[plot_col].mean()
            df_filtered['PPM'] = ((df_filtered[plot_col] - mean_val) / mean_val * 1_000_000) if mean_val != 0 else 0

            # --- 7. GRAPH (Timestamp X-Axis) ---
            selected_color = color_map.get(plot_col, "#1f77b4")
            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=x_axis_data, 
                y=df_filtered['PPM'], 
                mode='lines+markers',
                marker=dict(
                    color=df_filtered['PPM'],
                    colorscale=[[0, 'rgba(200,200,200,0.5)'], [1, selected_color]],
                    showscale=False,
                    size=7
                ),
                line=dict(color=selected_color, width=2),
                name=plot_col
            ))
            
            fig.update_layout(
                title=f"<b>{plot_col} Stability Over Time</b>",
                xaxis=dict(title=x_label, rangeslider=dict(visible=True)),
                yaxis=dict(title="PPM Deviation"),
                template="plotly_white",
                height=550
            )
            st.plotly_chart(fig, use_container_width=True)

            # --- 8. STATISTICS ---
            st.markdown("### 📊 Statistics Summary")
            c1, c2, c3 = st.columns(3)
            c1.metric("Mean Value", f"{mean_val:.4f}")
            c2.metric("Peak PPM", f"{df_filtered['PPM'].max():.2f}")
            c3.metric("Min PPM", f"{df_filtered['PPM'].min():.2f}")

            # --- 9. DATA TABLE ---
            st.subheader("📋 Filtered Results")
            display_cols = ([time_col] if time_col else []) + all_found + ( [temp_target] if temp_target in cols else [] ) + ['PPM']
            st.dataframe(df_filtered[display_cols], use_container_width=True)

        else:
            st.warning("⚠️ No data matches the selected filter range.")

else:
    st.info("👋 Upload a CSV file. The app will automatically map the Time Stamp from your file to the X-axis.")
