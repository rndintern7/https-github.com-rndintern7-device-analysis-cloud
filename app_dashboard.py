import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import base64
import os

# 1. Page Config
st.set_page_config(page_title="Device Analysis System", layout="wide")

# --- Function to load logo (Cached) ---
@st.cache_data
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
    st.caption("Performance Optimized Cloud Dashboard")

with col_logo:
    if logo_base64:
        st.markdown(f'<div style="text-align:right;"><img src="data:image/png;base64,{logo_base64}" style="width:180px;"></div>', unsafe_allow_html=True)

# --- 2. CACHED DATA LOADING ---
@st.cache_data
def load_and_clean_data(file):
    df = pd.read_csv(file)
    # Detect Time Column
    time_col = next((c for c in df.columns if "time" in c.lower()), None)
    if time_col:
        # Optimization: format='mixed' is much faster for mixed date strings
        df[time_col] = pd.to_datetime(df[time_col], errors='coerce')
    return df, time_col

# --- 3. CLOUD DATA UPLOADER ---
st.sidebar.header("📂 Data Source")
uploaded_file = st.sidebar.file_uploader("Upload your Dataset (CSV)", type=["csv"])

if uploaded_file is not None:
    # Use the cached loader
    df, time_col = load_and_clean_data(uploaded_file)
    cols = df.columns.tolist()
    
    # Define Targets
    mupt_targets = ["C1 Measurement", "C2 Measurement", "T1 Measurement", "T2 Measurement"]
    mtrol_targets = ["Flow Rate", "% Opening", "P1", "P2"]
    temp_target = "Chamber Temperature (°C)"
    
    found_mupt = [p for p in mupt_targets if p in cols]
    found_mtrol = [p for p in mtrol_targets if p in cols]
    is_mtrol = len(found_mtrol) > 0
    all_found = found_mupt + found_mtrol

    st.sidebar.markdown("---")
    st.sidebar.header("⚙️ Analysis Settings")
    
    if not all_found:
        st.error("⚠️ No target parameters found in CSV.")
    else:
        plot_col = st.sidebar.selectbox("Select Parameter to Analyze", all_found)

        # 4. FILTERS
        st.sidebar.markdown("---")
        st.sidebar.subheader("🎯 Data Filters")
        
        # Performance: Don't copy the whole DF if not needed
        if is_mtrol and temp_target in cols:
            target_temp = st.sidebar.slider("Target Chamber Temp (°C)", -40.0, 100.0, 70.0, 0.5)
            tol = st.sidebar.slider("Tolerance (+/- °C)", 0.1, 10.0, 1.0)
            df_filtered = df[
                (df[temp_target] >= target_temp - tol) & 
                (df[temp_target] <= target_temp + tol)
            ].copy()
        elif not is_mtrol:
            df_filtered = df.copy()
            for p in found_mupt:
                min_v, max_v = float(df[p].min()), float(df[p].max())
                r = st.sidebar.slider(f"Filter {p}", min_v, max_v, (min_v, max_v))
                df_filtered = df_filtered[(df_filtered[p] >= r[0]) & (df_filtered[p] <= r[1])]
        else:
            df_filtered = df.copy()

        if not df_filtered.empty:
            # 5. CALCULATIONS
            mean_val = df_filtered[plot_col].mean()
            df_filtered['PPM'] = ((df_filtered[plot_col] - mean_val) / mean_val * 1_000_000) if mean_val != 0 else 0

            # --- 6. OPTIMIZED GRAPH ---
            fig = go.Figure()
            fig.add_trace(go.Scattergl( # Scattergl is the WebGL version - MUCH FASTER for lag
                x=df_filtered[time_col] if time_col else list(range(len(df_filtered))), 
                y=df_filtered['PPM'], 
                mode='lines+markers',
                marker=dict(color="#1f77b4", size=6),
                line=dict(width=1.5),
                name=plot_col
            ))
            
            fig.update_layout(
                title=f"<b>{plot_col} Stability</b>",
                xaxis=dict(title=time_col if time_col else "Index"),
                yaxis=dict(title="PPM Deviation"),
                template="plotly_white",
                height=500,
                margin=dict(l=20, r=20, t=40, b=20)
            )
            # Setting use_container_width=True
            st.plotly_chart(fig, use_container_width=True)

            # --- 7. STATISTICS (Metrics are fast) ---
            st.markdown("### 📊 Statistics Summary")
            c1, c2, c3 = st.columns(3)
            c1.metric("Mean Value", f"{mean_val:.4f}")
            c2.metric("Peak PPM", f"{df_filtered['PPM'].max():.2f}")
            c3.metric("Min PPM", f"{df_filtered['PPM'].min():.2f}")

            # --- 8. DATA TABLE (Limited View for speed) ---
            st.subheader("📋 Filtered Results")
            st.dataframe(df_filtered.head(1000), use_container_width=True) # Limit to first 1000 rows for view speed

        else:
            st.warning("⚠️ No data matches the selected filter range.")
