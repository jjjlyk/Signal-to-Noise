# app.py — Signal to Noise: Dancing with the SARs
import os
import io
import json
import base64
import numpy as np
import streamlit as st
import streamlit.components.v1 as components
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

# Derived facts (computed from the data so the text never drifts from the numbers)
PEAK_ROW        = df_flood.loc[df_flood["Open Storm Flood (Ha)"].idxmax()]
PEAK_HIDDEN_ROW = df_flood.loc[df_flood["Hidden Flood (Ha)"].idxmax()]
BASELINE_DATES  = ["2026-07-05", "2026-07-17"]
LAST_ROW        = df_flood.iloc[-1]
RECESSION_PCT   = (1 - LAST_ROW["Open Storm Flood (Ha)"] / PEAK_ROW["Open Storm Flood (Ha)"]) * 100
PROVINCES       = df_mun["Province"].value_counts().index.tolist()

# SAR RGB composite channel assignment (confirmed by the processing pipeline)
SAR_RGB_CHANNELS = [
    ("#ff4d4d", "Red",   "HH (dB, stretched −25 to 0) — strong for double-bounce (flooded vegetation, buildings)"),
    ("#4dff88", "Green", "HV (dB, stretched −30 to −8) — strong for volume scattering (trees, dense canopy)"),
    ("#4d88ff", "Blue",  "HH − HV (dB, stretched 0 to 15) — the HH/HV ratio; high where double-bounce dominates"),
]

# ── SAR overlay helper ────────────────────────────────────────────────────────
@st.cache_data
def tif_to_png_base64(tif_path, max_width=None):
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
        if max_width and img.width > max_width:
            img = img.resize((max_width, round(img.height * max_width / img.width)))
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

# Flood duration palette: number of consecutive flooded NISAR passes → colour
DURATION_COLORS = {
    1: (255, 255, 178), 2: (254, 204, 92), 3: (253, 141, 60),
    4: (240, 59, 32),   5: (189, 0, 38),   6: (128, 0, 38),
}

@st.cache_data
def classes_to_png_base64(tif_path, palette):
    """Convert a single-band integer class GeoTIFF to a transparent PNG using a {value: rgb} palette."""
    try:
        import rasterio
        with rasterio.open(tif_path) as src:
            data = src.read(1)
        rgba = np.zeros((*data.shape, 4), dtype=np.uint8)
        for value, color in palette.items():
            rgba[data == value] = (*color, 255)
        img = Image.fromarray(rgba, mode="RGBA")
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return base64.b64encode(buf.getvalue()).decode()
    except Exception:
        return None

def legend_html(items, title=None):
    """Small inline legend: items = [(css_colour, label), ...]."""
    rows = "".join(
        f'<div style="display:flex;align-items:center;gap:8px;margin:3px 0;">'
        f'<span style="width:14px;height:14px;border-radius:3px;background:{c};'
        f'border:1px solid rgba(255,255,255,0.3);flex-shrink:0;"></span>'
        f'<span style="font-size:13px;">{label}</span></div>'
        for c, label in items
    )
    head = f'<div style="font-size:11px;letter-spacing:1px;color:#8ab4f8;margin-bottom:4px;">{title}</div>' if title else ""
    return f'<div style="padding:8px 12px;border:1px solid rgba(255,255,255,0.15);border-radius:8px;">{head}{rows}</div>'

# ── Page: Overview ────────────────────────────────────────────────────────────
if page == "🏠 Overview":
    st.title("🛰️ Dancing with the SARs")
    st.subheader("Candaba Swamp Flood & Agricultural Impact Monitor")
    st.markdown("""
    > *The Candaba Floodplain is one of the Philippines' largest freshwater wetlands —
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
    col3.metric("Peak Flood Date", f"{PEAK_ROW['Date']:%b} {PEAK_ROW['Date'].day}, {PEAK_ROW['Date'].year}",
                delta=f"{PEAK_ROW['Open Storm Flood (Ha)']:,.0f} Ha open flood", delta_color="off")
    col4.metric("NISAR Scenes",    f"{len(df_flood)} (Jun–Oct 2026)")
    st.caption(
        f"Hidden flood (water beneath vegetation) peaked later, on "
        f"{PEAK_HIDDEN_ROW['Date']:%b} {PEAK_HIDDEN_ROW['Date'].day} "
        f"({PEAK_HIDDEN_ROW['Hidden Flood (Ha)']:,.0f} Ha)."
    )

    st.markdown("---")
    st.subheader("📍 Why Candaba?")
    st.markdown("""
    Candaba is a **natural flood basin**. The swamp, about **32,000 Ha**, collects overflow from the Pampanga River system and
    from upstream provinces. It floods **every year**, which makes it a recurring problem rather than a one-off disaster.

    The land follows the water. From **November to April** the swamp is dry, and farmers grow **rice**
    (planted roughly November to June) and some **watermelon**. From about **July to October** the swamp floods, and much
    of its interior switches to **fish farming and duck raising**. Some farmers broadcast rice seed at the start of the rains
    (*sabog tuyo*). Those fields are directly exposed when the first big floods arrive in August.

    In August 2026 that is exactly what happened. Candaba recorded the **highest rice damage in Pampanga**.
    """)

    i1, i2, i3 = st.columns(3)
    i1.metric("Pampanga farm & fishery damage", "₱917.64M",
              help="Fisheries ₱496.53M · Rice ₱264.19M · High-value crops ₱125.81M "
                   "(TDs Luis, Maymay and Neneng, as of Aug 20, 2026)")
    i2.metric("Farmers & fisherfolk affected", "9,170")
    i3.metric("Candaba rice damage", "≈ ₱128M", help="Highest in the province")
    st.caption("Damage figures reported for Pampanga as of Aug 20, 2026.")

    st.markdown("---")
    st.info("📡 Data: NISAR L2 GCOV | Track 140A | Polarizations: HH + HV | Processed with Lee speckle filter")

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
    st.plotly_chart(fig_ov, width="stretch")

    # What the data shows, and why
    st.markdown("---")
    st.subheader("🔍 What we learned")
    st.markdown(f"""
    **1. NISAR caught the flood at its peak.** Jul 17 shows no flood above the pre-flood baseline. Then the southwest monsoon
    (*habagat*), strengthened by **Tropical Depressions Luis and Maymay** in early August, pushed the Pampanga River past
    critical level: on Aug 10 at 5 PM it stood at **5.60 m at Candaba** (critical: 5 m) and **8.20 m at Arayat** (critical: 8 m),
    and 291 barangays across Pampanga were flooded, with up to 11 ft of water in San Agustin, Candaba.
    NISAR's "Aug 10" pass was acquired at about **5:30 AM on Aug 11, Manila time**, roughly 12 hours later.
    It measured **{PEAK_ROW['Open Storm Flood (Ha)']:,.0f} Ha** of open storm flood, the highest of the season.

    **2. It drained slowly.** TD Neneng (Aug 18–20) never made landfall but strengthened the monsoon again, and the rains continued
    into September. On Sep 20, at least 80 barangays were still flooded, including Candaba (up to 6 ft), San Luis, Arayat and San Simon.
    NISAR shows the same thing from space: two months after the peak, **{LAST_ROW['Open Storm Flood (Ha)']:,.0f} Ha** was still under
    water. The open flood shrank by only **{RECESSION_PCT:.0f}%**. Candaba is a catch basin, so once the water arrives it has
    nowhere fast to go.

    **3. Hidden flood peaks after open flood.** Hidden flood (water beneath vegetation) peaked on
    {PEAK_HIDDEN_ROW['Date']:%b} {PEAK_HIDDEN_ROW['Date'].day}, after the open-water peak. Our hypothesis: as deep water recedes,
    grasses, aquatic plants and early-sown rice emerge above shallow standing water. "Open water" turns into "flooded vegetation",
    which only L-band radar can see through the canopy.

    **4. Farmland stays under water long enough to matter.** At the peak, **{PEAK_ROW['Flooded Cropland (Ha)']:,.0f} Ha** of
    cropland was flooded. Our at-risk layer marks cropland **under water for 12+ days (high risk of crop loss)**. Candaba
    municipality alone has **{df_mun.iloc[0]['At-Risk Cropland @ -14dB (Ha)']:,.0f} Ha** of it. Note that much of the
    swamp-interior farmland is used for fish and ducks in the wet season, so flooded cropland there is not all lost rice.
    """)

    st.subheader("🚀 What NISAR makes possible next")
    st.markdown("""
    - **Flood bulletins every 12 days for local governments** — NISAR's repeat cycle, through cloud and at night, fits the
      typhoon season when optical satellites are blind.
    - **Faster crop-insurance verification** — after the August storms, PCIC paid ₱187M to 24,987 insured farmers, and Central
      Luzon had the most beneficiaries (9,636). Maps showing which fields stayed under water, and for how long, could help check
      claims and target aid without waiting for field surveys.
    - **Adding to on-the-ground early warning** — the provincial disaster office already tracks Pampanga River levels and
      barangays run mobile warning patrols. NISAR adds the map view: where the water actually spread, even under cloud.
    - **Smarter planting calendars** — multi-year NISAR records could show which fields stay wet longest, helping farmers time
      planting around the flood pulse.
    - **Land subsidence monitoring** — NISAR's interferometry (InSAR) can measure centimetre-scale sinking, which deepens and
      lengthens floods in low-lying basins.
    """)

# ── Page: Flood Map ───────────────────────────────────────────────────────────
elif page == "🗺️ Flood Map":
    st.title("🗺️ Interactive Flood Map")

    date_options  = df_flood["Date"].dt.strftime("%Y-%m-%d").tolist()
    selected_date = st.select_slider(
        "Select scene date:", options=date_options,
        value=f"{PEAK_ROW['Date']:%Y-%m-%d}"
    )
    if selected_date in BASELINE_DATES:
        st.info("ℹ️ This is a pre-flood baseline scene. Flood is measured as change against it, so it reads 0 Ha.")

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
        "Flood Duration":       "⏳",
    }
    selected_overlay = st.selectbox(
        "Show flood classification overlay:",
        ["None"] + list(overlay_options.keys()) + ["Flood Duration"],
        help="Peak overlays show the worst extent of the season. "
             "Flood Duration shows how many consecutive NISAR passes each pixel stayed flooded."
    )
    if selected_overlay == "Flood Duration":
        dur_path = os.path.join(TIFS_DIR, "consecutive_flood_duration.tif")
        if os.path.exists(dur_path):
            with st.spinner("Loading flood duration…"):
                dur_b64 = classes_to_png_base64(dur_path, DURATION_COLORS)
            if dur_b64:
                folium.raster_layers.ImageOverlay(
                    image=f"data:image/png;base64,{dur_b64}",
                    bounds=[[BBOX[1], BBOX[0]], [BBOX[3], BBOX[2]]],
                    opacity=0.8,
                    name=f"{overlay_icons[selected_overlay]} Flood Duration",
                    interactive=True
                ).add_to(m)
            else:
                st.warning("⚠️ Could not render Flood Duration overlay")
        else:
            st.warning("⚠️ Overlay file not found: consecutive_flood_duration.tif")
    elif selected_overlay != "None":
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

    map_col, legend_col = st.columns([3, 1])
    with map_col:
        st_folium(m, height=580, use_container_width=True, returned_objects=[])
    with legend_col:
        if show_sar:
            st.markdown(legend_html(
                [(c, f"<b>{name}</b> = {desc}") for c, name, desc in SAR_RGB_CHANNELS],
                title="SAR RGB COMPOSITE"
            ), unsafe_allow_html=True)
            st.caption("Dark purple = water (radar reflects away from the satellite). "
                       "Yellow-green = vegetation, forest and towns.")
        if selected_overlay == "Flood Duration":
            st.markdown(legend_html(
                [(f"rgb{c}", f"{n} pass{'es' if n > 1 else ''} (~{n * 12} days)")
                 for n, c in DURATION_COLORS.items()],
                title="CONSECUTIVE FLOODED PASSES"
            ), unsafe_allow_html=True)
        elif selected_overlay != "None":
            label = ("Cropland under water 12+ days (high risk of crop loss)"
                     if selected_overlay == "Agricultural At-Risk" else selected_overlay)
            st.markdown(legend_html(
                [(f"rgb{overlay_options[selected_overlay][1]}", label)],
                title="FLOOD OVERLAY"
            ), unsafe_allow_html=True)
        st.markdown(legend_html(
            [("orange", "Key municipality (hover for stats)"),
             ("transparent;border:2px solid cyan", "NISAR scene boundary")],
            title="MAP FEATURES"
        ), unsafe_allow_html=True)

    # Before / after comparison slider
    st.markdown("---")
    st.subheader("↔️ Before vs. after")
    st.caption("Drag the handle to compare the pre-flood baseline with any later scene.")
    cmp1, cmp2 = st.columns(2)
    before_date = cmp1.selectbox("Before", date_options, index=date_options.index(BASELINE_DATES[-1]))
    after_date  = cmp2.selectbox("After",  date_options, index=date_options.index(f"{PEAK_ROW['Date']:%Y-%m-%d}"))
    before_b64 = tif_to_png_base64(
        os.path.join(TIFS_DIR, f"{before_date.replace('-', '')}_SAR_RGB_composite.tif"), max_width=1000)
    after_b64 = tif_to_png_base64(
        os.path.join(TIFS_DIR, f"{after_date.replace('-', '')}_SAR_RGB_composite.tif"), max_width=1000)
    if before_b64 and after_b64:
        components.html(f"""
        <div id="cmp" style="position:relative;max-width:680px;margin:auto;user-select:none;">
          <img src="data:image/png;base64,{after_b64}" style="width:100%;display:block;border-radius:8px;">
          <div id="clip" style="position:absolute;top:0;left:0;height:100%;width:50%;overflow:hidden;border-radius:8px 0 0 8px;">
            <img src="data:image/png;base64,{before_b64}" id="bimg" style="display:block;height:100%;max-width:none;">
          </div>
          <div id="bar" style="position:absolute;top:0;left:50%;height:100%;width:3px;background:#00bcd4;transform:translateX(-50%);"></div>
          <span style="position:absolute;top:8px;left:8px;background:rgba(0,0,0,.65);color:#fff;padding:2px 8px;border-radius:4px;font:13px sans-serif;">Before · {before_date}</span>
          <span style="position:absolute;top:8px;right:8px;background:rgba(0,0,0,.65);color:#fff;padding:2px 8px;border-radius:4px;font:13px sans-serif;">After · {after_date}</span>
          <input id="rng" type="range" min="0" max="100" value="50"
                 style="position:absolute;inset:0;width:100%;height:100%;opacity:0;cursor:ew-resize;margin:0;">
        </div>
        <script>
          const cmp = document.getElementById('cmp'), clip = document.getElementById('clip'),
                bar = document.getElementById('bar'), bimg = document.getElementById('bimg'),
                rng = document.getElementById('rng');
          const sync = () => {{ bimg.style.width = cmp.offsetWidth + 'px'; }};
          rng.addEventListener('input', e => {{ clip.style.width = e.target.value + '%'; bar.style.left = e.target.value + '%'; }});
          window.addEventListener('resize', sync); bimg.onload = sync; sync();
        </script>
        """, height=780)
    else:
        st.warning("⚠️ Could not load one of the selected SAR composites.")

# ── Page: Timeline ────────────────────────────────────────────────────────────
elif page == "📊 Timeline":
    st.title("📊 Flood Timeline — Jun to Oct 2026")
    st.markdown(f"Tracking the full monsoon and typhoon season across {len(df_flood)} NISAR passes.")

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

    # Pre-flood baseline band (reference scenes for change detection)
    fig.add_vrect(
        x0="2026-07-02", x1="2026-07-20",
        fillcolor="#4CAF50", opacity=0.12,
        annotation_text="Pre-flood baseline",
        annotation_position="top left"
    )
    # NISAR outage band
    fig.add_vrect(
        x0="2026-07-27", x1="2026-08-10",
        fillcolor="gray", opacity=0.2,
        annotation_text="NISAR outage",
        annotation_position="top left"
    )
    # Storm and on-the-ground events (drawn as shape + annotation; add_vline labels break on date axes)
    storm_events = [
        ("2026-08-05", "TDs Luis & Maymay"),
        ("2026-08-19", "TD Neneng"),
        ("2026-09-20", "80+ barangays<br>still flooded"),
    ]
    for i, (when, label) in enumerate(storm_events):
        fig.add_shape(type="line", x0=when, x1=when, y0=0, y1=1, yref="paper",
                      line=dict(color="#B39DDB", width=1, dash="dash"))
        fig.add_annotation(x=when, y=0.62 - 0.12 * (i % 2), yref="paper", text=label,
                           showarrow=False, font=dict(size=10, color="#D1C4E9"),
                           bgcolor="rgba(0,0,0,0.5)", xanchor="left", xshift=4)

    # Peak annotation
    fig.add_annotation(
        x=PEAK_ROW["Date"], y=PEAK_ROW["Open Storm Flood (Ha)"],
        text=f"Peak: {PEAK_ROW['Open Storm Flood (Ha)']:,.0f} Ha<br>{PEAK_ROW['Date']:%b} {PEAK_ROW['Date'].day} pass"
             f"<br><span style='font-size:10px'>(≈5:30 AM Aug 11, Manila time)</span>",
        showarrow=True, arrowhead=2,
        font=dict(color="white"), bgcolor="#333"
    )

    fig.update_layout(
        title="Candaba Floodplain — NISAR Flood Signal Over Time",
        xaxis_title="Date", yaxis_title="Area (Hectares)",
        template="plotly_dark", height=460,
        legend=dict(orientation="h", yanchor="bottom", y=1.02)
    )
    st.plotly_chart(fig, width="stretch")
    st.caption(
        "ℹ️ Jul 5 and Jul 17 are the pre-flood baseline scenes. Flood is measured as change "
        "against them, so they read 0 Ha by design. The 18,700 Ha of permanent water "
        "is included in Total Water on every date."
    )

    st.subheader("Data table")
    st.dataframe(
        df_flood.set_index("Date").style.highlight_max(color="#1a4a7a"),
        width="stretch"
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
    st.plotly_chart(fig, width="stretch")

    # Key metrics
    top_mun = df_mun.iloc[0]
    col1, col2 = st.columns(2)
    col1.metric("Most Affected",       f"{top_mun['Municipality']}, {top_mun['Province']}")
    col1.metric(f"{top_mun['Municipality']} At-Risk", f"{top_mun['At-Risk Cropland @ -14dB (Ha)']:,.0f} Ha")
    col2.metric("Total Municipalities", f"{len(df_mun)} across {len(PROVINCES)} provinces")
    col2.metric("Provinces",           " · ".join(PROVINCES))

    # Sensitivity comparison
    st.subheader("Threshold sensitivity: −14 dB vs −15 dB")
    st.caption(
        "A pixel counts as flooded when its radar backscatter falls below the threshold. "
        "−14 dB is our standard cut-off; −15 dB is stricter and only keeps the most confident water pixels. "
        "Municipalities whose numbers barely change are robust; big drops mean the estimate is less certain there."
    )
    fig2 = go.Figure()
    fig2.add_trace(go.Bar(
        name="@ −14 dB (standard)",
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
    st.plotly_chart(fig2, width="stretch")

    st.subheader("Full municipality table")
    st.dataframe(
        df_mun[["Municipality", "Province", "Grid Area (Ha)",
                "Peak Flood Area (Ha)",
                "At-Risk Cropland @ -14dB (Ha)",
                "At-Risk Cropland @ -15dB (Ha)"]],
        width="stretch"
    )
    st.caption(
        f"Municipal totals sum to {df_mun['At-Risk Cropland @ -14dB (Ha)'].sum():,.1f} Ha vs. "
        f"{summary['total_at_risk_cropland_hectares']:,.1f} Ha basin-wide. The basin-wide figure is computed "
        "over the whole scene, so it differs slightly from the sum of per-municipality figures."
    )

# ── Page: SAR Science ─────────────────────────────────────────────────────────
elif page == "📡 SAR Science":
    st.title("📡 How NISAR Sees the Flood")

    st.markdown("""
    ### Why L-band SAR detects floods — even under crops
    - NISAR sends out its own microwave pulses and listens for the echo (**backscatter**), so it works
      day or night and straight through typhoon clouds ☁️✅
    - Water has a high **dielectric constant**, so it acts like a mirror for radar. **Calm open water**
      bounces the pulse *away* from the satellite → very little echo → it looks **dark**.
    - L-band (24 cm wavelength) **penetrates the vegetation canopy** (grasses, aquatic plants, rice). When there is water underneath, the pulse
      bounces off the water, then off the stalks, and straight back (**double-bounce**) → the area looks
      **brighter** than dry fields, by roughly **+3 to +10 dB**.
    - So the same water looks **dark** when it is open and **bright** when it is hidden under crops —
      which is why we use two different tests to find each.
    """)

    st.markdown("---")
    col1, col2, col3 = st.columns(3)
    col1.info("**Backscatter < −14 dB**\n\nDark = open water (mirror-like reflection away from the sensor)")
    col2.warning("**HH rises ≥ +3 dB vs. baseline**\n\nBright = water hidden beneath vegetation")
    col3.error("**HH / HV ratio rises**\n\nDouble-bounce dominates = confirms flooded vegetation")

    with st.expander("📖 Glossary — radar terms in plain language"):
        st.markdown("""
        | Term | What it means |
        |---|---|
        | **Backscatter** | How much of the radar pulse comes back to the satellite. |
        | **dB (decibel)** | A log scale for backscatter. More negative = darker = less echo. −14 dB is quite dark. |
        | **HH** | Pulse sent and received **h**orizontally. Sensitive to double-bounce (flooded vegetation, buildings). |
        | **HV** | Sent **h**orizontal, received **v**ertical. Sensitive to messy "volume" scattering in leaves and branches. |
        | **HHHH / HVHV** | How NISAR's GCOV product names the HH and HV power layers. |
        | **Double-bounce** | Pulse hits water, then a stem (or wall), then returns — a strong, bright echo. |
        | **Speckle / Lee filter** | Radar images are naturally grainy ("speckle"); the Lee filter smooths it while keeping edges. |
        | **Otsu threshold** | An automatic way to pick the brightness cut-off that best separates two groups (water vs. land). |
        | **Baseline scene** | A pre-flood image (Jul 5, Jul 17) that later scenes are compared against to measure change. |
        """)

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
    | Polarizations | HH, HV (GCOV layers HHHH, HVHV) |
    | Repeat cycle | 12 days |
    | Track | 140 Ascending, Frame 9 |
    | Processing | PROVISIONAL V1 (CRID P05023) |

    ### Resources
    - [NISAR Data User Guide](https://nisar-docs.asf.alaska.edu/)
    - [ASF Data Search Vertex](https://search.asf.alaska.edu/)
    - [NISAR Applications — Societal Benefits](https://nisar.jpl.nasa.gov/applications/societal-benefit/)
    - [CSA SAR Python Tutorial](https://github.com/asc-csa/Synthetic_Aperture_Radar_Tutorial)
    """)