import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import base64
import os

# 1. Page Config
st.set_page_config(page_title="Device Analysis System", layout="wide")

# --- Logo Loader ---
@st.cache_data
def get_base64_image(image_path):
    try:
        if os.path.exists(image_path):
            with open(image_path, "rb") as img_file:
                return base64.b64encode(img_file.read()).decode()
        return ""
    except: return ""

logo_base64 = get_base64_image("logo.png")

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
col_title, col_logo = st.columns([8, 2])
with col_title:
    st.title("Device Analysis System")
    st.caption("Multi-Device Stability Analytics with Dynamic Legend")

with col_logo:
    if logo_base64:
        st.markdown(f'<div style="text-align:right;"><img src="data:image/png;base64,{logo_base64}" style="width:180px;"></div>', unsafe_allow_html=True)

# --- 3. DATA SOURCE ---
st.sidebar.header("📂 Data Source")
uploaded_file = st.sidebar.file_uploader("Upload Dataset (CSV)", type=["csv"])

if uploaded_file is not None:
    df, time_col = load_and_clean_data(uploaded_file)
    cols = df.columns.tolist()
    
    # --- 14 UNIQUE COLORS PALETTE ---
    color_map = {
        # MUPT (10 Parameters)
        "C1 Measurement": "#00CCFF", "C2 Measurement": "#33FFFF",
        "T1 Measurement": "#00FF99", "T2 Measurement": "#99FFCC",
        "Trap Mode": "#FF00FF", "Bypass Mode": "#FF66FF",
        "Solenoid Status": "#FFFF00", "Steam Leak": "#FFCC00",
        "Water Log/Process Off": "#FF9900", "Cooling Cycle Switch": "#00FFFF",
        # Mtrol 3 & 4 (4 Parameters)
        "Flow Rate": "#FF4B4B", "% Opening": "#FF8F8F",
        "P1": "#A64DFF", "P2": "#D9B3FF"
    }

    mupt_plot_only = ["C1 Measurement", "C2 Measurement", "T1 Measurement", "T2 Measurement",
                      "Trap Mode", "Bypass Mode", "Solenoid Status", "Steam Leak",
                      "Water Log/Process Off", "Cooling Cycle Switch"]
    mtrol_targets = ["Flow Rate", "% Opening", "P1", "P2"]
    temp_target = "Chamber Temperature (°C)"
    
    found_mupt = [p for p in mupt_plot_only if p in cols]
    found_mtrol = [p for p in mtrol_targets if p in cols]
    
    # Device Identification for Legend
    device_name = "MUPT" if len(found_mupt) > len(found_mtrol) else "Mtrol 3/4"
    all_plot_params = found_mupt + found_mtrol

    st.sidebar.markdown("---")
    st.sidebar.header("⚙️ Settings")
    
    if not all_plot_params:
        st.error("⚠️ No target parameters detected.")
    else:
        plot_col = st.sidebar.selectbox("Select Parameter to Analyze", all_plot_params)

        # 4. FILTERS
        st.sidebar.markdown("---")
        st.sidebar.subheader("🎯 Data Filters")
        df_filtered = df.copy()
        filter_text = "All Data"

        if device_name == "Mtrol 3/4" and temp_target in cols:
            target_temp = st.sidebar.slider("Target Chamber Temp (°C)", -40.0, 100.0, 70.0, 0.5)
            tol = st.sidebar.slider("Tolerance (+/- °C)", 0.1, 10.0, 1.0)
            df_filtered = df[(df[temp_target] >= target_temp - tol) & (df[temp_target] <= target_temp + tol)].copy()
            filter_text = f"Temp: {target_temp}°C ±{tol}°C"
        else:
            mupt_slider_targets = ["C1 Measurement", "C2 Measurement", "T1 Measurement", "T2 Measurement"]
            found_sliders = [p for p in mupt_slider_targets if p in cols]
            if found_sliders:
                filter_text = "Range Filtered"
                for p in found_sliders:
                    min_v, max_v = float(df[p].min()), float(df[p].max())
                    r = st.sidebar.slider(f"Filter {p}", min_v, max_v, (min_v, max_v))
                    df_filtered = df_filtered[(df_filtered[p] >= r[0]) & (df_filtered[p] <= r[1])]

        if not df_filtered.empty:
            # 5. CALCULATIONS
            is_numeric = pd.api.types.is_numeric_dtype(df_filtered[plot_col])
            mean_val = df_filtered[plot_col].mean() if is_numeric else 0
            
            if is_numeric and mean_val != 0:
                df_filtered['PPM'] = ((df_filtered[plot_col] - mean_val) / mean_val * 1_000_000)
                y_col, y_label = 'PPM', "PPM Deviation"
            else:
                y_col, y_label = plot_col, "Value/Status"

            # --- 6. GRAPH WITH DYNAMIC LEGEND ---
            selected_color = color_map.get(plot_col, "#FFFFFF")
            bg_color = "#0e1117" 
            grid_color = "#31333f"

            fig = go.Figure()
            fig.add_trace(go.Scattergl(
                x=df_filtered[time_col], y=df_filtered[y_col], 
                mode='lines+markers', connectgaps=True,
                marker=dict(color=selected_color, size=4),
                line=dict(color=selected_color, width=1.5),
                name=plot_col
            ))
            
            # Custom Annotation Legend (Right Most Top)
            legend_html = f"<b>Device:</b> {device_name}<br><b>Filter:</b> {filter_text}"
            
            fig.update_layout(
                title=f"<b>{plot_col} Analysis</b>",
                xaxis=dict(title="Time Stamp", gridcolor=grid_color,
                           rangeslider=dict(visible=True, bgcolor=bg_color, thickness=0.1, bordercolor=grid_color)),
                yaxis=dict(title=y_label, gridcolor=grid_color, zeroline=False),
                template="plotly_dark",
                plot_bgcolor=bg_color, paper_bgcolor=bg_color,
                height=600,
                annotations=[dict(
                    x=1, y=1.05, xref="paper", yref="paper",
                    text=legend_html, showarrow=False, align="right",
                    bgcolor="rgba(0,0,0,0.5)", bordercolor=grid_color, borderwidth=1, padding=10
                )]
            )
            
            st.plotly_chart(fig, use_container_width=True)

            # --- 7. STATISTICS ---
            st.markdown("### 📊 Statistics Summary")
            c1, c2, c3 = st.columns(3)
            if is_numeric and mean_val != 0:
                c1.metric("Mean Value", f"{mean_val:.4f}")
                c2.metric("Peak PPM", f"{df_filtered['PPM'].max():.2f}")
                c3.metric("Min PPM", f"{df_filtered['PPM'].min():.2f}")
            else:
                c1.info("Status-based parameter: No PPM calculation.")

            st.dataframe(df_filtered.head(500), use_container_width=True)
        else:
            st.warning("⚠️ No data matches the selected filters.")
