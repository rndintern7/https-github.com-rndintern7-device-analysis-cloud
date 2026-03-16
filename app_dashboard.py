import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import base64
import os

# 1. Page Config
st.set_page_config(page_title="Device Analysis System", layout="wide")

# --- Function to load logo ---
@st.cache_data
def get_base64_image(image_path):
    try:
        if os.path.exists(image_path):
            with open(image_path, "rb") as img_file:
                return base64.b64encode(img_file.read()).decode()
        return ""
    except: return ""

logo_base64 = get_base64_image("logo.png")

# --- 2. CACHED DATA LOADING ---
@st.cache_data
def load_and_clean_data(file):
    df = pd.read_csv(file)
    time_col = next((c for c in df.columns if "time" in c.lower()), None)
    if time_col:
        df[time_col] = pd.to_datetime(df[time_col], errors='coerce')
        df = df.sort_values(by=time_col)
    return df, time_col

# --- HEADER ---
col_title, col_logo = st.columns([8, 2])
with col_title:
    st.title("Device Analysis System")
    st.caption("Clean Visualization Mode: No Artifacts")

with col_logo:
    if logo_base64:
        st.markdown(f'<div style="text-align:right;"><img src="data:image/png;base64,{logo_base64}" style="width:180px;"></div>', unsafe_allow_html=True)

# --- 3. CLOUD DATA UPLOADER ---
st.sidebar.header("📂 Data Source")
uploaded_file = st.sidebar.file_uploader("Upload your Dataset (CSV)", type=["csv"])

if uploaded_file is not None:
    df, time_col = load_and_clean_data(uploaded_file)
    cols = df.columns.tolist()
    
    # High-contrast colors for Dark Mode
    color_map = {
        "C1 Measurement": "#00CCFF", "C2 Measurement": "#33FFFF",
        "T1 Measurement": "#00FF99", "T2 Measurement": "#99FFCC",
        "Flow Rate": "#FF4B4B", "% Opening": "#FF8F8F",
        "P1": "#FFAA00", "P2": "#FFD480"
    }

    mupt_targets = ["C1 Measurement", "C2 Measurement", "T1 Measurement", "T2 Measurement"]
    mtrol_targets = ["Flow Rate", "% Opening", "P1", "P2"]
    temp_target = "Chamber Temperature (°C)"
    
    found_mupt = [p for p in mupt_targets if p in cols]
    found_mtrol = [p for p in mtrol_targets if p in cols]
    is_mtrol = len(found_mtrol) > 0
    all_found = found_mupt + found_mtrol

    st.sidebar.markdown("---")
    st.sidebar.header("⚙️ Settings")
    
    if not all_found:
        st.error("⚠️ No target parameters detected.")
    else:
        plot_col = st.sidebar.selectbox("Select Parameter", all_found)

        # 4. FILTERS
        st.sidebar.markdown("---")
        st.sidebar.subheader("🎯 Data Filters")
        
        if is_mtrol and temp_target in cols:
            target_temp = st.sidebar.slider("Target Chamber Temp (°C)", -40.0, 100.0, 70.0, 0.5)
            tol = st.sidebar.slider("Tolerance (+/- °C)", 0.1, 10.0, 1.0)
            df_filtered = df[(df[temp_target] >= target_temp - tol) & (df[temp_target] <= target_temp + tol)].copy()
        else:
            df_filtered = df.copy()
            for p in found_mupt:
                min_v, max_v = float(df[p].min()), float(df[p].max())
                r = st.sidebar.slider(f"Filter {p}", min_v, max_v, (min_v, max_v))
                df_filtered = df_filtered[(df_filtered[p] >= r[0]) & (df_filtered[p] <= r[1])]

        if not df_filtered.empty:
            mean_val = df_filtered[plot_col].mean()
            df_filtered['PPM'] = ((df_filtered[plot_col] - mean_val) / mean_val * 1_000_000) if mean_val != 0 else 0

            # --- 6. CLEAN GRAPH (No WebGL, No Rangeslider) ---
            selected_color = color_map.get(plot_col, "#00CCFF")
            
            fig = go.Figure()
            # go.Scatter is smoother/cleaner than go.Scattergl for artifact-free viewing
            fig.add_trace(go.Scatter(
                x=df_filtered[time_col] if time_col else list(range(len(df_filtered))), 
                y=df_filtered['PPM'], 
                mode='lines+markers',
                connectgaps=True,
                marker=dict(color=selected_color, size=5),
                line=dict(color=selected_color, width=2),
                name=plot_col
            ))
            
            # Match Streamlit Dark Theme precisely
            bg_color = "#0e1117" 
            grid_color = "#31333f"

            fig.update_layout(
                title=f"<b>{plot_col} Stability</b>",
                xaxis=dict(
                    title="Time Stamp" if time_col else "Index",
                    gridcolor=grid_color,
                    zeroline=False,
                    rangeslider=dict(visible=False) # Rangeslider often causes white patches
                ),
                yaxis=dict(
                    title="PPM Deviation",
                    gridcolor=grid_color,
                    zeroline=False
                ),
                template="plotly_dark",
                plot_bgcolor=bg_color,
                paper_bgcolor=bg_color,
                margin=dict(l=40, r=40, t=60, b=40),
                height=550
            )
            
            st.plotly_chart(fig, use_container_width=True)

            # --- 7. STATISTICS ---
            st.markdown("### 📊 Statistics Summary")
            c1, c2, c3 = st.columns(3)
            c1.metric("Mean Value", f"{mean_val:.4f}")
            c2.metric("Peak PPM", f"{df_filtered['PPM'].max():.2f}")
            c3.metric("Min PPM", f"{df_filtered['PPM'].min():.2f}")

            st.subheader("📋 Data Preview")
            st.dataframe(df_filtered.head(500), use_container_width=True)
        else:
            st.warning("⚠️ No data in selected range.")
