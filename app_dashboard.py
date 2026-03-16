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
    st.caption("Cloud Analytics: Upload any CSV for automatic parameter detection.")

with col_logo:
    if logo_base64:
        st.markdown(f'<div style="text-align:right;"><img src="data:image/png;base64,{logo_base64}" style="width:180px;"></div>', unsafe_allow_html=True)

# --- 2. CLOUD DATA UPLOADER ---
st.sidebar.header("📂 Data Source")
uploaded_file = st.sidebar.file_uploader("Upload your Dataset (CSV)", type=["csv"])

if uploaded_file is not None:
    df = pd.read_csv(uploaded_file)
    cols = df.columns.tolist()
    
    # 3. AUTOMATIC PARAMETER DETECTION
    # Define all possible target parameters
    mupt_targets = ["C1 Measurement", "C2 Measurement", "T1 Measurement", "T2 Measurement"]
    mtrol_targets = ["Flow Rate", "% Opening", "P1", "P2"]
    
    # Check which ones exist in the file
    found_mupt = [p for p in mupt_targets if p in cols]
    found_mtrol = [p for p in mtrol_targets if p in cols]
    
    # Combine all found parameters for selection
    all_found = found_mupt + found_mtrol

    if not all_found:
        st.error("⚠️ No standard parameters (C1, T1, Flow Rate, etc.) found in this CSV. Please check headers.")
    else:
        st.sidebar.markdown("---")
        st.sidebar.header("⚙️ Analysis Settings")
        
        # User chooses which parameter to graph
        plot_col = st.sidebar.selectbox("Select Parameter to Analyze", all_found)

        # 4. DYNAMIC SLIDER FILTERS (Only for detected parameters)
        st.sidebar.markdown("---")
        st.sidebar.subheader("🎯 Data Filters")
        
        df_filtered = df.copy()
        
        for p in all_found:
            min_v, max_v = float(df[p].min()), float(df[p].max())
            # Add sliders for every relevant parameter found in the file
            r = st.sidebar.slider(f"Filter {p}", min_v, max_v, (min_v, max_v))
            df_filtered = df_filtered[(df_filtered[p] >= r[0]) & (df_filtered[p] <= r[1])]

        if not df_filtered.empty:
            # 5. CALCULATIONS
            mean_val = df_filtered[plot_col].mean()
            df_filtered['PPM'] = ((df_filtered[plot_col] - mean_val) / mean_val * 1_000_000) if mean_val != 0 else 0

            # --- 6. GRAPH (Sequence Index X-Axis) ---
            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=list(range(1, len(df_filtered) + 1)), 
                y=df_filtered['PPM'], 
                mode='lines+markers', 
                line=dict(color="#1f77b4", width=2),
                name=plot_col
            ))
            
            fig.update_layout(
                title=f"<b>Stability Analysis: {plot_col}</b>",
                xaxis=dict(title="Sequence Index (Data Points)", rangeslider=dict(visible=True)),
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
            table_cols = all_found + ['PPM']
            st.dataframe(df_filtered[table_cols], use_container_width=True, hide_index=False)

        else:
            st.warning("No data matches the selected filter ranges.")

else:
    st.info("👋 Welcome! Please upload your CSV file in the sidebar to begin. The system will automatically detect if it is an Mtrol or MUPT dataset.")
