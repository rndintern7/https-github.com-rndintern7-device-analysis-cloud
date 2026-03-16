import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import base64

# 1. Page Config
st.set_page_config(page_title="Cloud Device Analytics", layout="wide")

# --- Branding Logic ---
def get_base64_image(image_path):
    try:
        with open(image_path, "rb") as img_file:
            return base64.b64encode(img_file.read()).decode()
    except: return ""

logo_base64 = get_base64_image("logo.png")

col_title, col_logo = st.columns([8, 2])
with col_title:
    st.title("☁️ Device Analysis System (Cloud)")
    st.caption("Upload Mtrol or MUPT CSV files for stability analysis.")

with col_logo:
    if logo_base64:
        st.markdown(f'<div style="text-align:right;"><img src="data:image/png;base64,{logo_base64}" style="width:180px;"></div>', unsafe_allow_html=True)

# --- 2. CLOUD DATA UPLOADER ---
st.sidebar.header("📂 Data Source")
uploaded_file = st.sidebar.file_uploader("Upload your Dataset (CSV)", type=["csv"])

if uploaded_file is not None:
    # Read the uploaded file
    df = pd.read_csv(uploaded_file)
    all_cols = df.columns.tolist()

    st.sidebar.markdown("---")
    st.sidebar.header("⚙️ Settings")

    # 3. DYNAMIC COLUMN SELECTION
    # Try to auto-detect the Time column
    time_defaults = [c for c in all_cols if "time" in c.lower() or "date" in c.lower()]
    time_col = st.sidebar.selectbox("Select Time Column", all_cols, 
                                    index=all_cols.index(time_defaults[0]) if time_defaults else 0)

    # Filter out numeric columns for plotting
    numeric_cols = df.select_dtypes(include=['number']).columns.tolist()
    plot_col = st.sidebar.selectbox("Select Parameter to Analyze", numeric_cols)

    # 4. DYNAMIC FILTERS
    st.sidebar.markdown("---")
    st.sidebar.subheader("🎯 Data Filters")
    
    df_filtered = df.copy()
    # Add a slider for the selected plot column automatically
    min_v, max_v = float(df[plot_col].min()), float(df[plot_col].max())
    r = st.sidebar.slider(f"Filter {plot_col} Range", min_v, max_v, (min_v, max_v))
    df_filtered = df_filtered[(df_filtered[plot_col] >= r[0]) & (df_filtered[plot_col] <= r[1])]

    if not df_filtered.empty:
        # 5. CALCULATIONS
        # Convert time column to datetime
        df_filtered[time_col] = pd.to_datetime(df_filtered[time_col])
        mean_val = df_filtered[plot_col].mean()
        df_filtered['PPM'] = ((df_filtered[plot_col] - mean_val) / mean_val * 1_000_000) if mean_val != 0 else 0

        # --- 6. GRAPH ---
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=df_filtered[time_col], 
            y=df_filtered['PPM'], 
            mode='lines+markers', 
            line=dict(color="#1f77b4", width=2),
            name=plot_col
        ))
        
        fig.update_layout(
            title=f"<b>Stability Analysis: {plot_col}</b>",
            xaxis=dict(title=time_col, rangeslider=dict(visible=True)),
            yaxis=dict(title="PPM Deviation"),
            template="plotly_white",
            height=550,
            showlegend=True
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
        st.dataframe(df_filtered[[time_col, plot_col, 'PPM']], use_container_width=True, hide_index=True)

    else:
        st.warning("No data found for the selected filter range.")

else:
    # Initial state when no file is uploaded
    st.info("👋 Welcome! Please upload your CSV file in the sidebar to begin.")
