# app.py — Signal to Noise: Dancing with the SARs
import os
import io
import json
import base64
import numpy as np
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import folium
from streamlit_folium import st_folium
from PIL import Image

st.set_page_config(
    page_title="Signal to Noise | Candaba Flood Monitor",
    page_icon="🛰️",
    layout="wide"
)

# ── Paths ─────────────────────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
TIFS_DIR = os.path.join(BASE_DIR, "tifs")

# ── Sidebar ───────────────────────────────────────────────────────────────────
st.sidebar.image("https://www.nasa.gov/wp-content/themes/nasa/assets/images/nasa-logo.svg", width=120)
st.sidebar.title("🛰️ Signal to Noise")
st.sidebar.markdown("**Dancing with the SARs**\nNASA Space Apps 2026")
st.sidebar.markdown("---")
page = st.sidebar.radio("Navigate", [
    "🏠 Overview",
    "🗺️ Flood Map",
    "📊 Timeline",
    "🌾 Agricultural Impact",
    "📡 SAR Science"
])

# ── Load data ─────────────────────────────────────────────────────────────────
@st.cache_data
def load_data():
    df_flood = pd.read_csv(os.path.join(DATA_DIR, "flood_impact_stats.csv"))
    df_mun   = pd.read_csv(os.path.join(DATA_DIR, "municipality_rankings.csv"))
    with open(os.path.join(DATA_DIR, "bounds_summary.json")) as f:
        summary = json.load(f)
    return df_flood, df_mun, summary

df_flood, df_mun, summary = load_data()
df_flood["Date"] = pd.to_datetime(df_flood["Date"], format="%Y%m%d")

BBOX   = (120.65, 14.85, 121.05, 15.30)
CENTER = [15.075, 120.85]

# ── SAR overlay helper ────────────────────────────────────────────────────────
@st.cache_data
def tif_to_png_base64(tif_path):
    """Convert a SAR RGB GeoTIFF to a base64 PNG for Folium overlay."""
    try:
        import rasterio
        with rasterio.open(tif_path) as src:
            r = src.read(1).astype(np.float32)
            g = src.read(2).astype(np.float32)
            b = src.read(3).astype(np.float32)
        def norm(arr):
            arr = np.clip(arr, 0, 255)
            return arr.astype(np.uint8)
        rgb = np.dstack([norm(r), norm(g), norm(b)])
        img = Image.fromarray(rgb)
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return base64.b64encode(buf.getvalue()).decode()
    except Exception:
        return None

@st.cache_data
def mask_to_png_base64(tif_path, color):
    """Convert a single-band 0/1 mask GeoTIFF to a transparent, colored base64 PNG."""
    try:
        import rasterio
        with rasterio.open(tif_path) as src:
            mask = src.read(1) > 0
        rgba = np.zeros((*mask.shape, 4), dtype=np.uint8)
        rgba[mask] = (*color, 255)
        img = Image.fromarray(rgba, mode="RGBA")
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return base64.b64encode(buf.getvalue()).decode()
    except Exception:
        return None

# ── Page: Overview ────────────────────────────────────────────────────────────
if page == "🏠 Overview":
    st.title("🛰️ Dancing with the SARs")
    st.subheader("Candaba Swamp Flood & Agricultural Impact Monitor")
    st.markdown("""
    > *The Candaba Floodplain is the Philippines' largest freshwater wetland —
    > and Central Luzon's rice granary. Every typhoon season, it floods.
    > NISAR lets us watch it happen from space, in any weather, day or night.*
    """)

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Cropland",
                f"{summary['total_cropland_hectares']:,.0f} Ha")
    col2.metric("At-Risk Cropland",
                f"{summary['total_at_risk_cropland_hectares']:,.0f} Ha",
                delta=f"{summary['total_at_risk_cropland_hectares'] / summary['total_cropland_hectares'] * 100:.1f}% of total",
                delta_color="inverse")
    col3.metric("Peak Flood Date", "Sep 3, 2026")
    col4.metric("NISAR Scenes",    "9 (Jun–Oct 2026)")

    st.markdown("---")
    st.info("📡 Data: NISAR L2 GCOV | Track 140A | Polarization: HHHH + HVHV | Processed with Lee speckle filter")

    # Quick summary chart
    st.subheader("Flood extent at a glance")
    fig_ov = go.Figure()
    fig_ov.add_trace(go.Bar(
        x=df_flood["Date"].dt.strftime("%b %d"),
        y=df_flood["Open Storm Flood (Ha)"],
        name="Open Storm Flood", marker_color="#2196F3"
    ))
    fig_ov.add_trace(go.Bar(
        x=df_flood["Date"].dt.strftime("%b %d"),
        y=df_flood["Hidden Flood (Ha)"],
        name="Hidden Flood", marker_color="#FF9800"
    ))
    fig_ov.update_layout(
        barmode="stack", template="plotly_dark",
        xaxis_title="Date", yaxis_title="Area (Ha)",
        height=300, margin=dict(t=20)
    )
    st.plotly_chart(fig_ov, use_container_width=True)

# ── Page: Flood Map ───────────────────────────────────────────────────────────
elif page == "🗺️ Flood Map":
    st.title("🗺️ Interactive Flood Map")

    date_options  = df_flood["Date"].dt.strftime("%Y-%m-%d").tolist()
    selected_date = st.select_slider(
        "Select scene date:", options=date_options, value="2026-09-03"
    )

    # Flood stats for selected date
    sel = df_flood[df_flood["Date"].dt.strftime("%Y-%m-%d") == selected_date].iloc[0]
    c1, c2, c3 = st.columns(3)
    c1.metric("Open Storm Flood", f"{sel['Open Storm Flood (Ha)']:,.0f} Ha")
    c2.metric("Hidden Flood",     f"{sel['Hidden Flood (Ha)']:,.0f} Ha")
    c3.metric("Flooded Cropland", f"{sel['Flooded Cropland (Ha)']:,.0f} Ha")

    # SAR overlay toggle
    show_sar = st.checkbox("🛰️ Show SAR RGB composite overlay", value=True)

    m = folium.Map(location=CENTER, zoom_start=12, tiles=None)

    # Named basemaps (shown as radio buttons in the layer control)
    folium.TileLayer(
        tiles="https://tiles.stadiamaps.com/tiles/alidade_smooth_dark/{z}/{x}/{y}{r}.png",
        attr='© <a href="https://stadiamaps.com/">Stadia Maps</a> © <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
        name="Dark Basemap"
    ).add_to(m)
    folium.TileLayer(
        tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
        attr="Tiles © Esri — Source: Esri, Maxar, Earthstar Geographics",
        name="Optical Satellite (Esri)"
    ).add_to(m)

    # Dark-themed layer control styling
    m.get_root().header.add_child(folium.Element("""
    <style>
    .leaflet-control-layers {
        background: rgba(14, 17, 23, 0.92) !important;
        color: #e6e6e6 !important;
        border: 1px solid rgba(0, 255, 255, 0.35) !important;
        border-radius: 8px !important;
        font-family: 'Source Sans Pro', sans-serif;
        font-size: 13px;
        padding: 6px 10px !important;
    }
    .leaflet-control-layers-base::before {
        content: "BASEMAP";
        display: block; font-size: 10px; letter-spacing: 1px;
        color: #8ab4f8; margin-bottom: 4px;
    }
    .leaflet-control-layers-overlays::before {
        content: "NISAR DATA LAYERS";
        display: block; font-size: 10px; letter-spacing: 1px;
        color: #8ab4f8; margin-bottom: 4px;
    }
    .leaflet-control-layers-separator { border-top-color: rgba(255,255,255,0.15) !important; }
    .leaflet-control-layers label { margin: 3px 0; }
    .leaflet-control-layers input { accent-color: #00bcd4; }
    </style>
    """))

    # SAR RGB GeoTIFF overlay (changes with date slider)
    if show_sar:
        date_nodash = selected_date.replace("-", "")
        tif_path = os.path.join(TIFS_DIR, f"{date_nodash}_SAR_RGB_composite.tif")
        if os.path.exists(tif_path):
            with st.spinner("Loading SAR imagery…"):
                img_b64 = tif_to_png_base64(tif_path)
            if img_b64:
                folium.raster_layers.ImageOverlay(
                    image=f"data:image/png;base64,{img_b64}",
                    bounds=[[BBOX[1], BBOX[0]], [BBOX[3], BBOX[2]]],
                    opacity=0.65,
                    name=f"🛰️ NISAR SAR Composite · {pd.to_datetime(selected_date):%b %d, %Y}",
                    interactive=True
                ).add_to(m)
        else:
            st.warning(f"⚠️ No SAR composite found for {selected_date}")

    # Flood overlay TIFs (peak storm / hidden / agricultural)
    overlay_options = {
        "Peak Storm Flood":     ("peak_storm_flood_overlay.tif",              (33, 150, 243)),
        "Peak Hidden Flood":    ("peak_hidden_flood_overlay.tif",             (255, 152, 0)),
        "Agricultural At-Risk": ("agricultural_cropland_at_risk_overlay.tif", (244, 67, 54)),
    }
    overlay_icons = {
        "Peak Storm Flood":     "🟦",
        "Peak Hidden Flood":    "🟧",
        "Agricultural At-Risk": "🟥",
    }
    selected_overlay = st.selectbox(
        "Show flood classification overlay:",
        ["None"] + list(overlay_options.keys())
    )
    if selected_overlay != "None":
        overlay_file, overlay_color = overlay_options[selected_overlay]
        overlay_path = os.path.join(TIFS_DIR, overlay_file)
        if os.path.exists(overlay_path):
            with st.spinner("Loading flood overlay…"):
                ov_b64 = mask_to_png_base64(overlay_path, overlay_color)
            if ov_b64:
                folium.raster_layers.ImageOverlay(
                    image=f"data:image/png;base64,{ov_b64}",
                    bounds=[[BBOX[1], BBOX[0]], [BBOX[3], BBOX[2]]],
                    opacity=0.75,
                    name=f"{overlay_icons[selected_overlay]} {selected_overlay}",
                    interactive=True
                ).add_to(m)
            else:
                st.warning(f"⚠️ Could not render {selected_overlay} overlay")
        else:
            st.warning(f"⚠️ Overlay file not found: {overlay_file}")

    # AOI boundary
    aoi_layer = folium.FeatureGroup(name="⬜ NISAR Scene Boundary")
    folium.Rectangle(
        bounds=[[BBOX[1], BBOX[0]], [BBOX[3], BBOX[2]]],
        color="cyan", fill=False, weight=2,
        tooltip="NISAR AOI — Candaba Swamp"
    ).add_to(aoi_layer)
    aoi_layer.add_to(m)

    # Municipality markers
    mun_coords = {
        "Candaba":  [15.09, 120.83],
        "Arayat":   [15.15, 120.76],
        "San Luis": [15.04, 120.79],
        "Cabiao":   [15.24, 120.84],
        "Apalit":   [14.95, 120.76],
    }
    mun_layer = folium.FeatureGroup(name="🟠 Key Municipalities")
    for mun, coords in mun_coords.items():
        row = df_mun[df_mun["Municipality"] == mun]
        if not row.empty:
            risk  = row["At-Risk Cropland @ -14dB (Ha)"].values[0]
            flood = row["Peak Flood Area (Ha)"].values[0]
            folium.CircleMarker(
                coords, radius=9, color="orange",
                fill=True, fill_opacity=0.8,
                tooltip=f"<b>{mun}</b><br>At-Risk Cropland: {risk:,.0f} Ha<br>Peak Flood: {flood:,.0f} Ha"
            ).add_to(mun_layer)
    mun_layer.add_to(m)

    folium.LayerControl(collapsed=True).add_to(m)
    st_folium(m, width=900, height=580)

    st.caption("🟠 Circle markers = key municipalities | 🟦 Cyan box = NISAR scene boundary | 🛰️ SAR composite changes with date slider")

# ── Page: Timeline ────────────────────────────────────────────────────────────
elif page == "📊 Timeline":
    st.title("📊 Flood Timeline — Jun to Oct 2026")
    st.markdown("Tracking the full monsoon and typhoon season across 9 NISAR passes.")

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df_flood["Date"], y=df_flood["Open Storm Flood (Ha)"],
        name="Open Storm Flood", fill="tozeroy",
        line=dict(color="#2196F3", width=2)
    ))
    fig.add_trace(go.Scatter(
        x=df_flood["Date"], y=df_flood["Hidden Flood (Ha)"],
        name="Hidden Flood (under crops)", fill="tozeroy",
        line=dict(color="#FF9800", width=2)
    ))
    fig.add_trace(go.Scatter(
        x=df_flood["Date"], y=df_flood["Flooded Cropland (Ha)"],
        name="Flooded Cropland",
        line=dict(color="#F44336", width=3, dash="dot")
    ))

    # NISAR outage band
    fig.add_vrect(
        x0="2026-07-27", x1="2026-08-10",
        fillcolor="gray", opacity=0.2,
        annotation_text="NISAR outage",
        annotation_position="top left"
    )
    # Peak annotation
    fig.add_annotation(
        x="2026-08-10", y=21240,
        text="Peak: 21,240 Ha<br>Aug 10",
        showarrow=True, arrowhead=2,
        font=dict(color="white"), bgcolor="#333"
    )

    fig.update_layout(
        title="Candaba Floodplain — NISAR Flood Signal Over Time",
        xaxis_title="Date", yaxis_title="Area (Hectares)",
        template="plotly_dark", height=460,
        legend=dict(orientation="h", yanchor="bottom", y=1.02)
    )
    st.plotly_chart(fig, use_container_width=True)

    st.subheader("Data table")
    st.dataframe(
        df_flood.set_index("Date").style.highlight_max(color="#1a4a7a"),
        use_container_width=True
    )

# ── Page: Agricultural Impact ─────────────────────────────────────────────────
elif page == "🌾 Agricultural Impact":
    st.title("🌾 Agricultural Impact by Municipality")

    top_n  = st.slider("Show top N municipalities", 5, 20, 10)
    df_top = df_mun.head(top_n)

    # Bar chart
    fig = px.bar(
        df_top,
        x="At-Risk Cropland @ -14dB (Ha)",
        y="Municipality",
        orientation="h",
        color="Province",
        hover_data=["Peak Flood Area (Ha)", "At-Risk Cropland @ -15dB (Ha)"],
        title=f"Top {top_n} Municipalities by At-Risk Cropland",
        template="plotly_dark",
        color_discrete_sequence=px.colors.qualitative.Bold
    )
    fig.update_layout(height=520)
    st.plotly_chart(fig, use_container_width=True)

    # Key metrics
    col1, col2 = st.columns(2)
    col1.metric("Most Affected",       "Candaba, Pampanga")
    col1.metric("Candaba At-Risk",     "4,130 Ha")
    col2.metric("Total Municipalities", f"{len(df_mun)} across 3 provinces")
    col2.metric("Provinces",           "Pampanga · Nueva Ecija · Bulacan")

    # Sensitivity comparison
    st.subheader("Threshold sensitivity: −14 dB vs −15 dB")
    fig2 = go.Figure()
    fig2.add_trace(go.Bar(
        name="@ −14 dB (baseline)",
        x=df_top["Municipality"],
        y=df_top["At-Risk Cropland @ -14dB (Ha)"],
        marker_color="#2196F3"
    ))
    fig2.add_trace(go.Bar(
        name="@ −15 dB (strict)",
        x=df_top["Municipality"],
        y=df_top["At-Risk Cropland @ -15dB (Ha)"],
        marker_color="#FF9800"
    ))
    fig2.update_layout(
        barmode="group", template="plotly_dark",
        xaxis_title="Municipality", yaxis_title="At-Risk Cropland (Ha)",
        height=380
    )
    st.plotly_chart(fig2, use_container_width=True)

    st.subheader("Full municipality table")
    st.dataframe(
        df_mun[["Municipality", "Province", "Grid Area (Ha)",
                "Peak Flood Area (Ha)",
                "At-Risk Cropland @ -14dB (Ha)",
                "At-Risk Cropland @ -15dB (Ha)"]],
        use_container_width=True
    )

# ── Page: SAR Science ─────────────────────────────────────────────────────────
elif page == "📡 SAR Science":
    st.title("📡 How NISAR Sees the Flood")

    st.markdown("""
    ### Why L-band SAR detects floods under vegetation
    - Water has a high **dielectric constant** → reflects radar strongly
    - L-band (24 cm wavelength) **penetrates crop canopy** to reach floodwater below
    - Flooded rice paddies show **double-bounce** scattering — signal bounces off water then crop stalks
    - This raises backscatter by **+3 to +10 dB** vs dry land
    - Even under thick typhoon cloud cover → SAR still works ☁️✅
    """)

    st.markdown("---")
    col1, col2, col3 = st.columns(3)
    col1.info("**Backscatter < −14 dB**\n\nOpen water / flooded surface")
    col2.warning("**+3 dB change (HH)**\n\nCanopy flood signal — hidden beneath rice")
    col3.error("**HH − HV ratio rises**\n\nDouble-bounce = confirmed flooded crops")

    st.markdown("---")
    st.markdown("""
    ### Processing pipeline used in this project
    1. **Download** — NISAR L2 GCOV HDF5 via ASF Earthdata (9 scenes, Track 140A)
    2. **Crop** — Extract Candaba AOI from each ~5 GB scene → ~40 MB
    3. **Despeckle** — Lee filter (5×5 window) to reduce radar speckle noise
    4. **Convert** — Linear power → decibels (dB scale)
    5. **Reproject** — Native UTM → WGS84 (EPSG:4326) for mapping
    6. **Classify** — Otsu threshold → Open water / Storm flood / Hidden flood / Land
    7. **Measure** — Pixel-area weighted statistics per municipality

    ### Sensor specs
    | Parameter | Value |
    |---|---|
    | Satellite | NISAR (NASA / ISRO) |
    | Band | L-band (24 cm wavelength) |
    | Polarizations | HHHH, HVHV (GCOV) |
    | Repeat cycle | 12 days |
    | Track | 140 Ascending, Frame 9 |
    | Processing | PROVISIONAL V1 (CRID P05023) |

    ### Resources
    - [NISAR Data User Guide](https://nisar-docs.asf.alaska.edu/)
    - [ASF Data Search Vertex](https://search.asf.alaska.edu/)
    - [NISAR Floods White Paper](https://nisar.jpl.nasa.gov/applications/societal-benefit/)
    - [CSA SAR Python Tutorial](https://github.com/asc-csa/Synthetic_Aperture_Radar_Tutorial)
    """)