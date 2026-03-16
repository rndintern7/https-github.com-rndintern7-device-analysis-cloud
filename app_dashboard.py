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
    st.caption("Upload your CSV and select product mode for specific parameter analysis.")

with col_logo:
    if logo_base64:
        st.markdown(f'<div style="text-align:right;"><img src="data:image/png;base64,{logo_base64}" style="width:180px;"></div>', unsafe_allow_html=True)

# --- 2. CLOUD DATA UPLOADER ---
st.sidebar.header("📂 Data Source")
uploaded_file = st.sidebar.file_uploader("Upload your Dataset (CSV)", type=["csv"])

if uploaded_file is not None:
    df = pd.read_csv(uploaded_file)
    
    # 3. DEVICE SELECTION
    st.sidebar.markdown("---")
    st.sidebar.header("⚙️ Device Mode")
    device = st.sidebar.selectbox("Select Product", ["Mtrol 3", "Mtrol 4", "MUPT"])

    # Define Parameters based on your requirements
    if device == "MUPT":
        target_params = ["C1 Measurement", "C2 Measurement", "T1 Measurement", "T2 Measurement"]
    else:
        # For Mtrol 3 & 4
        target_params = ["Flow Rate", "% Opening", "P1", "P2"]

    # Only show parameters that actually exist in the uploaded CSV
    available_params = [p for p in target_params if p in df.columns]
    
    if not available_params:
        st.error(f"⚠️ None of the required parameters for {device} were found in the CSV. Please check your headers.")
    else:
        plot_col = st.sidebar.selectbox("Select Parameter to Analyze", available_params)

        # 4. DYNAMIC SLIDER FILTERS
        st.sidebar.markdown("---")
        st.sidebar.subheader("🎯 Data Filters")
        
        df_filtered = df.copy()
        
        # Create sliders for all target parameters for that device
        for p in available_params:
            min_v, max_v = float(df[p].min()), float(df[p].max())
            # Default to full range
            r = st.sidebar.slider(f"Filter {p}", min_v, max_v, (min_v, max_v))
            df_filtered = df_filtered[(df_filtered[p] >= r[0]) & (df_filtered[p] <= r[1])]

        if not df_filtered.empty:
            # 5. CALCULATIONS (Using Index for X-axis instead of Time)
            mean_val = df_filtered[plot_col].mean()
            df_filtered['PPM'] = ((df_filtered[plot_col] - mean_val) / mean_val * 1_000_000) if mean_val != 0 else 0

            # --- 6. GRAPH (X-axis is now Data Points/Index) ---
            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=list(range(len(df_filtered))), # Removed Time, using sequence index
                y=df_filtered['PPM'], 
                mode='lines+markers', 
                line=dict(color="#1f77b4", width=2),
                name=plot_col
            ))
            
            fig.update_layout(
                title=f"<b>{device} Stability: {plot_col}</b>",
                xaxis=dict(title="Data Point Index", rangeslider=dict(visible=True)),
                yaxis=dict(title="PPM Deviation"),
                template="plotly_white",
                height=550
            )
            st.plotly_chart(fig, use_container_width=True)

            # --- 7. STATISTICS ---
            st.markdown("### 📊 Statistics Summary")
            c1, c2, c3 = st.columns(3)
            c1.metric("Mean Value", f"{mean_val:.4f}")
            c2.metric("Peak PPM", f"{df_filtered['PPM'].max():.2f}")
            c3.metric("Min PPM", f"{df_filtered['PPM'].min():.2f}")

            # --- 8. DATA TABLE ---
            st.subheader("📋 Filtered Results")
            # Only show relevant columns in table
            table_cols = available_params + ['PPM']
            st.dataframe(df_filtered[table_cols], use_container_width=True, hide_index=False)

        else:
            st.warning("No data found for the selected filter ranges.")

else:
    st.info("👋 Welcome! Please upload your CSV file in the sidebar to begin.")
