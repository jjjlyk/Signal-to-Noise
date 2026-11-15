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
    page_icon=":material/satellite_alt:",
    layout="wide"
)

# ── Paths ─────────────────────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
TIFS_DIR = os.path.join(BASE_DIR, "tifs")
TEAM_DIR = os.path.join(BASE_DIR, "assets", "team")
PLACE_DIR = os.path.join(BASE_DIR, "assets", "candaba")
LOGO_PATH = os.path.join(BASE_DIR, "assets", "logo", "signal_to_noise_white_logo.png")

# ── Candaba photos ────────────────────────────────────────────────────────────
CANDABA_PHOTOS = [
    {"file": "candaba_1.jpg", "source": "Expedia",       "url": "https://www.expedia.com/Candaba.dx553248634304933708"},
    {"file": "candaba_2.jpg", "source": "Lakad Pilipinas", "url": "https://www.lakadpilipinas.com/2011/04/candaba-glorious-sunrise.html"},
    {"file": "candaba_3.jpg", "source": "GMA News",      "url": "https://www.gmanetwork.com/news/topstories/regions/1001490/da-eyes-candaba-swamp-waterway-project-to-curb-flooding/story/"},
]

# ── Team & project links ──────────────────────────────────────────────────────
TEAM_MEMBERS = [
    {"name": "Jelyka Mae Dizon",   "role": "Web App Developer", "photo": "Dizon, Jelyka Mae.jpg",
     "links": {"GitHub":   "https://github.com/jjjlyk",
               "LinkedIn": "https://www.linkedin.com/in/jelyka-mae-dizon-1b2753327"}},
    {"name": "Chrysler James Gaa",   "role": "Flood Analysis and Impact Lead",   "photo": "Gaa, Chrysler James.png",
     "links": {"GitHub":   "https://github.com/rysll",
               "LinkedIn": "https://www.linkedin.com/in/chrysler-james-gaa-359576328/"}},
    {"name": "Rishon Simone Papa", "role": "SAR Data Acquisition and Preprocessing Lead",  "photo": "Papa, Rishon Simone.jpe",
     "links": {"GitHub":   "https://github.com/RSVPapa",
               "LinkedIn": "https://www.linkedin.com/in/rishon-simone-papa-519516333/"}},
]
PROJECT_LINKS = {
    "colab":  "https://colab.research.google.com/drive/1zNbjOiFXpkCnQGa0v0q8sB_8D6jxiVPV?usp=sharing",
    "github": "https://github.com/jjjlyk/Signal-to-Noise",
}
SOCIAL_ICONS = {"LinkedIn": ":material/work:", "GitHub": ":material/code:", "Facebook": ":material/group:",
                "Instagram": ":material/photo_camera:", "Website": ":material/language:", "Email": ":material/mail:"}

# ── Load data ─────────────────────────────────────────────────────────────────
@st.cache_data
def load_data():
    df_flood = pd.read_csv(os.path.join(DATA_DIR, "flood_impact_stats.csv"))
    df_mun   = pd.read_csv(os.path.join(DATA_DIR, "municipality_rankings.csv"), encoding="utf-8")
    df_sens  = pd.read_csv(os.path.join(DATA_DIR, "sensitivity_check.csv"))
    with open(os.path.join(DATA_DIR, "bounds.json")) as f:
        meta = json.load(f)
    return df_flood, df_mun, df_sens, meta

df_flood, df_mun, df_sens, META = load_data()
df_flood["Date"] = pd.to_datetime(df_flood["Date"], format="%Y%m%d")

BBOX   = tuple(META["bbox_wgs84"])
BOUNDS = META["leaflet_bounds"]
CENTER = [(BBOX[1] + BBOX[3]) / 2, (BBOX[0] + BBOX[2]) / 2]

def fmt_date(d):
    """'20260810' or Timestamp → 'Aug 10'."""
    d = pd.to_datetime(d, format="%Y%m%d") if isinstance(d, str) else d
    return f"{d:%b} {d.day}"

def iso(d):
    """'20260810' → '2026-08-10'."""
    return f"{d[:4]}-{d[4:6]}-{d[6:]}"

THR, THR_STRICT = META["water_threshold_db"], META["sensitivity_threshold_db"]
RISK_COL        = f"At-Risk Cropland @ {THR} dB (Ha)"
RISK_COL_STRICT = f"At-Risk Cropland @ {THR_STRICT} dB (Ha)"
PEAK_MUN_COL    = f"Peak Flood {META['peak_storm_flood_date']} (Ha)"

PEAK_ROW        = df_flood[df_flood["Date"] == pd.to_datetime(META["peak_storm_flood_date"])].iloc[0]
BASELINE_DATES  = [iso(d) for d in META["baseline_dates"]]
CHECK_DATE      = iso(META["check_date"])
FALSE_ALARM_HA  = META["false_alarm_margin_ha"]
CHECK_ROW       = df_flood[df_flood["Role"] == "check"].iloc[0]
LAST_ROW        = df_flood.iloc[-1]
RECESSION_PCT   = (1 - LAST_ROW["Open Storm Flood (Ha)"] / PEAK_ROW["Open Storm Flood (Ha)"]) * 100
ERROR_MARGIN_HA = round(META["false_alarm_margin_ha"], -2)
TOTAL_AT_RISK_STRICT = META["total_at_risk_cropland_ha_strict"]
HIDDEN_NOTE = ("Experimental, not validated: hidden flood is only searched for within about 500 m of open flood, "
               "so its trend follows open flood and is not an independent result.")
HIDDEN_RULE = ("a pixel is flagged when HH brightens by more than 3 dB compared with the pre-storm average, more than "
               "2 dB more than HV, and it lies within about 500 m of open flood. This is the double-bounce signature "
               "of water under standing crops.")
PROVINCES       = df_mun["Province"].value_counts().index.tolist()
TOTAL_CROPLAND  = df_mun["Cropland (Ha)"].sum()
TOTAL_AT_RISK   = META["total_at_risk_cropland_ha"]
RISK_PASSES     = META["consecutive_passes_for_risk"]
RISK_DAYS       = (RISK_PASSES - 1) * 12
ROLE_LABELS     = {"check": "False-alarm check", "baseline": "Pre-flood baseline", "post-storm": "Post-storm"}

DISPLAY_COLS = {
    PEAK_MUN_COL:    f"Flood on {pd.to_datetime(META['peak_storm_flood_date']):%b} "
                     f"{pd.to_datetime(META['peak_storm_flood_date']).day} (Ha)",
    RISK_COL:        f"At-Risk Cropland @ {THR:g} dB (Ha)",
    RISK_COL_STRICT: f"At-Risk Cropland @ {THR_STRICT:g} dB (Ha)",
}

SAR_RGB_CHANNELS = [
    ("#ff4d4d", "Red",   f"{META['rgb_bands']['red']} — strong for double-bounce (flooded vegetation, buildings)"),
    ("#4dff88", "Green", f"{META['rgb_bands']['green']} — strong for volume scattering (trees, dense canopy)"),
    ("#4d88ff", "Blue",  f"{META['rgb_bands']['blue']} — the HH/HV ratio; high where double-bounce dominates"),
]

THEMATIC_CLASSES = {
    1: ((96, 125, 139),  "Normal water (river, ponds, usual swamp water)"),
    2: ((33, 150, 243),  "Storm flood (open water outside usual water)"),
    3: ((255, 152, 0),   "Hidden flood (experimental): water beneath vegetation"),
}

# ── Helpers ───────────────────────────────────────────────────────────────────
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
        alpha = np.where((rgb == 0).all(axis=2), 0, 255).astype(np.uint8)
        img = Image.fromarray(np.dstack([rgb, alpha]), mode="RGBA")
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
            mask = src.read(1) == 1
        rgba = np.zeros((*mask.shape, 4), dtype=np.uint8)
        rgba[mask] = (*color, 255)
        img = Image.fromarray(rgba, mode="RGBA")
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return base64.b64encode(buf.getvalue()).decode()
    except Exception:
        return None

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
    """Small inline legend: items = [(css_colour, label), ...]. A colour of 'outline:<css colour>' draws a hollow box."""
    def swatch_style(c):
        if c.startswith("outline:"):
            return f"background:transparent;border:2px solid {c.split(':', 1)[1]};"
        return f"background:{c};border:1px solid rgba(255,255,255,0.3);"
    rows = "".join(
        f'<div style="display:flex;align-items:center;gap:8px;margin:3px 0;">'
        f'<span style="width:14px;height:14px;border-radius:3px;box-sizing:border-box;{swatch_style(c)}'
        f'flex-shrink:0;"></span>'
        f'<span style="font-size:13px;">{label}</span></div>'
        for c, label in items
    )
    head = f'<div style="font-size:11px;letter-spacing:1px;color:#8ab4f8;margin-bottom:4px;">{title}</div>' if title else ""
    return f'<div style="padding:8px 12px;border:1px solid rgba(255,255,255,0.15);border-radius:8px;margin-bottom:8px;">{head}{rows}</div>'

AVATAR_COLORS = ["linear-gradient(135deg,#00bcd4,#3f51b5)",
                 "linear-gradient(135deg,#ff9800,#e91e63)",
                 "linear-gradient(135deg,#8bc34a,#009688)"]

@st.cache_data
def photo_base64(file_name, folder=TEAM_DIR, max_width=1200):
    """Photo from an assets folder as a base64 JPEG data URI (shrunk to max_width), or None if it isn't there yet."""
    path = os.path.join(folder, file_name or "")
    if not file_name or not os.path.isfile(path):
        return None
    img = Image.open(path).convert("RGB")
    if img.width > max_width:
        img = img.resize((max_width, round(img.height * max_width / img.width)), Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=85)
    return f"data:image/jpeg;base64,{base64.b64encode(buf.getvalue()).decode()}"

@st.cache_data
def logo_base64(path):
    """Transparent PNG logo cropped to its visible content, as a base64 data URI (None if missing)."""
    if not os.path.isfile(path):
        return None
    img = Image.open(path).convert("RGBA")
    img = img.crop(img.getchannel("A").getbbox() or (0, 0, *img.size))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return f"data:image/png;base64,{base64.b64encode(buf.getvalue()).decode()}"

def avatar_html(member, index, size=96, ring="rgba(255,255,255,0.15)"):
    """Round photo, or coloured initials when no photo has been added."""
    style = f"width:{size}px;height:{size}px;border-radius:50%;border:2px solid {ring};flex-shrink:0;"
    src = photo_base64(member.get("photo"), TEAM_DIR, max_width=320)
    if src:
        return f'<img src="{src}" alt="{member["name"]}" style="{style}object-fit:cover;object-position:center 20%;">'
    initials = "".join(w[0] for w in member["name"].split()[:2]).upper()
    return (f'<div style="{style}background:{AVATAR_COLORS[index % len(AVATAR_COLORS)]};display:flex;'
            f'align-items:center;justify-content:center;color:white;font-weight:700;'
            f'font-size:{int(size * 0.36)}px;">{initials}</div>')

def slideshow_html(photos, folder, height=360, interval_ms=5000):
    """Auto-advancing photo slideshow with arrows and dots. Missing photos show a placeholder."""
    slides = []
    for i, p in enumerate(photos):
        src = photo_base64(p["file"], folder)
        body = (f'<img src="{src}" alt="Candaba photo {i + 1}">' if src else
                f'<div class="ph"><svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="#9aa0a6" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="9" cy="9" r="2"/><path d="m21 15-5-5L5 21"/></svg>'
                f'<div>Add a photo: <code>assets/candaba/{p["file"]}</code></div></div>')
        slides.append(f'<div class="slide{" on" if i == 0 else ""}">{body}</div>')
    dots = "".join(f'<span class="dot{" on" if i == 0 else ""}" onclick="go({i})"></span>' for i in range(len(photos)))
    return f"""
    <style>
      body {{ margin:0; font-family:'Source Sans Pro',sans-serif; }}
      .show {{ position:relative; height:{height}px; border-radius:12px; overflow:hidden; background:#1e1e1e; }}
      .slide {{ position:absolute; inset:0; opacity:0; transition:opacity .8s ease; }}
      .slide.on {{ opacity:1; }}
      .slide img {{ width:100%; height:100%; object-fit:cover; display:block; }}
      .ph {{ height:100%; display:flex; flex-direction:column; align-items:center; justify-content:center; gap:8px;
             color:#9aa0a6; font-size:14px; background:linear-gradient(135deg,#1f2a36,#263238); }}
      .ph code {{ color:#8ab4f8; }}
      .nav {{ position:absolute; top:50%; transform:translateY(-50%); width:34px; height:34px; border-radius:50%;
              border:none; background:rgba(0,0,0,.45); color:#fff; font-size:18px; cursor:pointer; }}
      .nav:hover {{ background:rgba(0,188,212,.6); }}
      .prev {{ left:10px; }} .next {{ right:10px; }}
      .dots {{ position:absolute; top:10px; right:12px; display:flex; gap:6px; }}
      .dot {{ width:9px; height:9px; border-radius:50%; background:rgba(255,255,255,.45); cursor:pointer; }}
      .dot.on {{ background:#00bcd4; }}
    </style>
    <div class="show" onmouseenter="paused=true" onmouseleave="paused=false">
      {''.join(slides)}
      <button class="nav prev" onclick="go(cur-1)" aria-label="Previous photo">&#8249;</button>
      <button class="nav next" onclick="go(cur+1)" aria-label="Next photo">&#8250;</button>
      <div class="dots">{dots}</div>
    </div>
    <script>
      let cur = 0, paused = false;
      const s = document.querySelectorAll('.slide'), d = document.querySelectorAll('.dot');
      function go(i) {{
        s[cur].classList.remove('on'); d[cur].classList.remove('on');
        cur = (i + s.length) % s.length;
        s[cur].classList.add('on'); d[cur].classList.add('on');
      }}
      setInterval(() => {{ if (!paused) go(cur + 1); }}, {interval_ms});
    </script>
    """

def layer_swatch(background, border="1px solid rgba(255,255,255,0.35)", round_=False):
    """Small coloured square (or dot) shown before a layer name in the map's layer menu."""
    return (f'<span style="display:inline-block;width:11px;height:11px;margin-right:6px;vertical-align:-1px;'
            f'box-sizing:border-box;background:{background};border:{border};'
            f'border-radius:{"50%" if round_ else "2px"};"></span>')

def duration_label(n):
    """Consecutive flooded passes → plain-language duration (passes are 12 days apart)."""
    return "Flooded on 1 pass" if n == 1 else f"{n} passes in a row (≥ {(n - 1) * 12} days)"

# ── Page: Overview ────────────────────────────────────────────────────────────
def page_overview():
    st.title(":material/satellite_alt: Dancing with the SARs")
    st.subheader("Candaba Swamp Flood & Agricultural Impact Monitor")
    st.markdown("""
    > *The Candaba Floodplain is one of the Philippines' largest freshwater wetlands
    > and Central Luzon's rice granary. Every typhoon season, it floods.
    > NISAR lets us watch it happen from space, in any weather, day or night.*
    """)

    col1, col2, col3, col4 = st.columns([1, 1.5, 1.3, 0.9])
    col1.metric("Total Cropland", f"{TOTAL_CROPLAND:,.0f} Ha",
                help="ESA WorldCover 2021 cropland inside the study-area municipalities")
    col2.metric("Cropland at High Risk", f"{TOTAL_AT_RISK_STRICT:,.0f}–{TOTAL_AT_RISK:,.0f} Ha",
                delta=f"up to {TOTAL_AT_RISK / TOTAL_CROPLAND * 100:.1f}% of cropland",
                delta_color="inverse", delta_arrow="off",
                help=f"Cropland flooded on {RISK_PASSES}+ consecutive NISAR passes ({RISK_DAYS}+ days): high risk of "
                     f"crop loss, not confirmed damage. Range = {THR_STRICT:g} dB (strict) to {THR:g} dB (standard).")
    col3.metric("Peak Flood Date", f"{fmt_date(PEAK_ROW['Date'])}, {PEAK_ROW['Date'].year}",
                delta=f"{PEAK_ROW['Open Storm Flood (Ha)']:,.0f} ± {ERROR_MARGIN_HA:,.0f} Ha open flood",
                delta_color="off", delta_arrow="off",
                help=f"Error margin from the {fmt_date(META['check_date'])} pre-storm false-alarm check")
    col4.metric("NISAR Scenes",    f"{len(df_flood)} (Jun–Oct 2026)")

    st.markdown("---")
    st.subheader(":material/location_on: Why Candaba?")
    why_text, why_photos = st.columns([3, 2], gap="large")
    with why_photos:
        st.iframe(slideshow_html(CANDABA_PHOTOS, PLACE_DIR), height=370)
    why_text.markdown("""
    Candaba is a **natural flood basin**. It collects overflow from the Pampanga River system and from upstream provinces,
    and plays an important role in **storing floodwaters** for the region. The swamp's extent varies by definition and
    season. It floods **every year**, which makes it a recurring problem rather than a one-off disaster.

    The land follows the water. From **late November to April** most of the swamp dries out and is turned into **rice
    fields and watermelon plantations**. In the wet season the whole area is usually flooded: impounded areas become
    **fishponds**, and farmers raise **ducks**. Some farmers broadcast rice seed at the start of the rains
    (*sabog tuyo*). Those fields are directly exposed when the first big floods arrive in August.

    In August 2026, Candaba recorded the **highest rice damage in Pampanga**.
    """)

    i1, i2, i3 = st.columns(3)
    i1.metric("Pampanga farm & fishery damage", "₱917.64M",
              help="Fisheries ₱496.53M · Rice ₱264.19M · High-value crops ₱125.81M "
                   "(TDs Luis, Maymay and Neneng, as of Aug 20, 2026)")
    i2.metric("Farmers & fisherfolk affected", "9,170")
    i3.metric("Candaba rice damage", "≈ ₱128M", help="Highest in the province")
    st.caption("Damage figures reported for Pampanga as of Aug 20, 2026 "
               "([SunStar Pampanga](https://www.sunstar.com.ph/pampanga/pampanga-agri-damage-climbs-to-p9176-m)).")

    st.markdown("---")
    def chips(items):
        return "".join(f'<span style="display:inline-block;padding:3px 10px;margin:3px 6px 3px 0;border-radius:999px;'
                       f'background:rgba(138,180,248,0.12);border:1px solid rgba(138,180,248,0.25);'
                       f'font-size:13px;color:#cfe0ff;">{t}</span>' for t in items)
    label = ('font-size:11px;letter-spacing:1px;color:#8ab4f8;font-weight:600;'
             'padding-top:7px;white-space:nowrap;')
    st.markdown(f"""
    <div style="display:grid;grid-template-columns:max-content 1fr;column-gap:18px;row-gap:6px;
                padding:12px 16px;border-radius:10px;background:rgba(28,131,225,0.10);
                border:1px solid rgba(138,180,248,0.18);">
      <div style="{label}">NISAR DATA</div>
      <div>{chips(["L2 GCOV", "Track 140A, Frame 9", "HH + HV polarizations", "Lee speckle filter"])}</div>
      <div style="{label}">CONTEXT LAYERS</div>
      <div>{chips(["ESA WorldCover 2021 · cropland", "JRC Global Surface Water · usual water",
                   "geoBoundaries · municipalities"])}</div>
    </div>
    """, unsafe_allow_html=True)

    st.subheader("Flood extent at a glance")
    st.markdown(
        f"How much new flooding NISAR saw on each of its {len(df_flood)} passes over the study area. "
        f"**Blue** is open storm flood: open water outside the usual river, fishponds and swamp water. "
        f"**Orange** is hidden flood under vegetation (experimental). The **dotted line** is our error margin: "
        f"on {fmt_date(META['check_date'])}, before any storm, the method still flagged about "
        f"{ERROR_MARGIN_HA:,.0f} Ha, so bars near that line are not a confident flood signal."
    )
    is_check = df_flood["Role"] == "check"
    is_base  = df_flood["Role"] == "baseline"
    labels   = df_flood["Date"].dt.strftime("%b %d")
    hover    = "%{x}: %{y:,.0f} Ha<extra>%{fullData.name}</extra>"
    fig_ov = go.Figure()
    fig_ov.add_trace(go.Bar(
        x=labels[is_check], y=df_flood.loc[is_check, "Open Storm Flood (Ha)"],
        name="False-alarm check (error margin)", marker_color="#607D8B", hovertemplate=hover
    ))
    fig_ov.add_trace(go.Bar(
        x=labels[~is_check], y=df_flood.loc[~is_check, "Open Storm Flood (Ha)"],
        name="Open storm flood", marker_color="#2196F3",
        hovertemplate=f"%{{x}}: %{{y:,.0f}} ± {ERROR_MARGIN_HA:,.0f} Ha<extra>Open storm flood</extra>"
    ))
    fig_ov.add_trace(go.Bar(
        x=labels[~is_check], y=df_flood.loc[~is_check, "Hidden Flood (Ha)"],
        name="Hidden flood (experimental)", marker_color="#FF9800", hovertemplate=hover
    ))
    fig_ov.add_hline(
        y=FALSE_ALARM_HA, line=dict(color="#B0BEC5", width=1.5, dash="dot"),
        annotation_text=f"Error margin ≈ ±{ERROR_MARGIN_HA:,.0f} Ha",
        annotation_position="top right", annotation_font=dict(size=11, color="#CFD8DC")
    )
    for x in labels[is_base]:
        fig_ov.add_annotation(x=x, y=0, yshift=14, text="baseline<br>(0 by design)", showarrow=False,
                              font=dict(size=10, color="#9E9E9E"))
    fig_ov.update_layout(
        barmode="stack", template="plotly_dark",
        xaxis_title="NISAR pass date", yaxis_title="Area (Ha)",
        height=340, margin=dict(t=30),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0)
    )
    st.plotly_chart(fig_ov, width="stretch")

    st.markdown("---")
    st.subheader(":material/lightbulb: What we learned")
    st.markdown(f"""
    **1. NISAR caught the flood at its peak.** The two July passes are our pre-flood baseline. Then the southwest monsoon
    (*habagat*), strengthened by **TD Luis** (landfall in Maconacon, Isabela on Aug 3) and **Maymay** (a tropical storm by
    Aug 5), pushed the Pampanga River past
    critical level: on Aug 10 at 5 PM it stood at **5.60 m at Candaba** (critical: 5 m) and **8.20 m at Arayat** (critical: 8 m),
    and 291 barangays across Pampanga were flooded, with up to 11 ft of water in San Agustin, Candaba.
    NISAR's "Aug 10" pass was acquired at about **5:30 AM on Aug 11, Manila time**, roughly 12 hours later.
    It measured **{PEAK_ROW['Open Storm Flood (Ha)']:,.0f} ± {ERROR_MARGIN_HA:,.0f} Ha** of open storm flood, the highest of the season.

    **2. It drained slowly.** TD Neneng (Aug 18–20) never made landfall but strengthened the monsoon again, and the rains continued
    into September. On Sep 20, at least 80 barangays were still flooded, including Candaba (up to 6 ft), San Luis, Arayat and San Simon.
    NISAR shows the same thing from space: two months after the peak, **{LAST_ROW['Open Storm Flood (Ha)']:,.0f} Ha** was still under
    water, even though the open flood had shrunk by **{RECESSION_PCT:.0f}%**. Candaba is a catch basin, so once the water
    arrives it has nowhere fast to go.

    **3. Some water hides under vegetation (experimental).** L-band radar can see water beneath grasses, aquatic plants and
    rice through double-bounce, which optical satellites cannot. On {fmt_date(PEAK_ROW['Date'])} we flagged
    **{PEAK_ROW['Hidden Flood (Ha)']:,.0f} Ha** of this hidden flood: {HIDDEN_RULE} Treat it as a demonstration of what
    NISAR can do, not a validated result. Because we only search near open flood, it rises and falls with open flood by design.

    **4. Farmland stays under water long enough to matter.** At the peak, **{PEAK_ROW['Flooded Cropland (Ha)']:,.0f} Ha** of
    cropland was flooded. **{TOTAL_AT_RISK_STRICT:,.0f}–{TOTAL_AT_RISK:,.0f} Ha** stayed under water for **{RISK_DAYS}+ days**
    ({THR_STRICT:g} dB to {THR:g} dB threshold): **cropland at high risk of crop loss**, not confirmed damage. Candaba
    municipality alone has **{df_mun.iloc[0][RISK_COL_STRICT]:,.0f}–{df_mun.iloc[0][RISK_COL]:,.0f} Ha** of it. In the wet
    season much of the swamp interior is fishponds or fallow land, so this is not all rice.

    **5. We measured our own error.** {fmt_date(CHECK_DATE.replace('-', ''))}, before any storm, is a **false-alarm check**: the method
    still flagged **{FALSE_ALARM_HA:,.0f} Ha** as storm flood and **{CHECK_ROW['Hidden Flood (Ha)']:,.0f} Ha** as hidden flood there.
    Those are our error margins. On {fmt_date(PEAK_ROW['Date'])}, storm flood was **about
    {PEAK_ROW['Open Storm Flood (Ha)'] / FALSE_ALARM_HA:.0f} times the false-alarm level** (hidden flood about
    {PEAK_ROW['Hidden Flood (Ha)'] / CHECK_ROW['Hidden Flood (Ha)']:.0f} times).
    Using a stricter {THR_STRICT:g} dB threshold shrinks every number by 20–32%, but the story — fast rise, slow drain — stays the same.
    """)

    st.subheader(":material/rocket_launch: What NISAR makes possible next")
    st.markdown("""
    - **Flood bulletins every 12 days for local governments** — NISAR's repeat cycle, through cloud and at night, fits the
      typhoon season when optical satellites are blind.
    - **Faster crop-insurance verification** — after the August storms, PCIC paid ₱187M to 24,987 insured farmers, and Central
      Luzon had the most beneficiaries (9,636). Maps showing which fields stayed under water, and for how long, could help check
      claims and target aid without waiting for field surveys.
    - **Adding to on-the-ground early warning** — the provincial disaster office already tracks Pampanga River levels and
      barangays run mobile warning patrols. NISAR adds the map view: where the water actually spread, even under cloud.
    - **Planning flood-control works** — the Department of Agriculture has commissioned a ₱150M feasibility study for large
      canals in the Candaba Swamp. Season-by-season NISAR flood maps could show planners where water collects and how long it stays.
    - **Smarter planting calendars** — multi-year NISAR records could show which fields stay wet longest, helping farmers time
      planting around the flood pulse.
    - **Land subsidence monitoring** — NISAR's interferometry (InSAR) can measure centimetre-scale sinking, which deepens and
      lengthens floods in low-lying basins.
    """)

    with st.expander(":material/menu_book: Sources for the local context on this page"):
        st.markdown("""
        **Storms and flooding**
        - [Flooded villages reach 291 as of August 10](https://www.sunstar.com.ph/pampanga/flooded-villages-reach-291-as-of-august-10) — SunStar Pampanga
        - [TD Luis makes landfall over Maconacon, Isabela](https://www.dzrh.com.ph/post/td-luis-makes-landfall-over-maconacon-isabela) — DZRH
        - [PAGASA raises Signal No. 2 as Maymay becomes tropical storm](https://mb.com.ph/2026/08/05/pagasa-raises-signal-no-2-over-6-luzon-areas-as-maymay-becomes-tropical-storm) — Manila Bulletin
        - [LPA develops into Tropical Depression Neneng](https://mb.com.ph/2026/08/18/lpa-develops-into-tropical-depression-neneng) — Manila Bulletin
        - [Neneng weakens into an LPA, exits PAR](https://mb.com.ph/2026/08/20/neneng-weakens-into-an-lpa-exits-philippine-area-of-responsibility) — Manila Bulletin
        - [Habagat puts Pampanga under state of calamity](https://www.manilatimes.net/2026/08/14/regions/habagat-puts-pampanga-under-state-of-calamity/2404999) — The Manila Times
        - [88 areas under state of calamity due to Habagat, Luis, Maymay](https://www.gmanetwork.com/news/topstories/nation/999337/88-areas-under-state-of-calamity-due-to-habagat-luis-maymay/story/) — GMA News
        - [80 villages in Pampanga still flooded — PDRRMO](https://www.sunstar.com.ph/pampanga/80-villages-in-pampanga-still-flooded-pdrrmo) — SunStar Pampanga

        **Candaba and its farms**
        - Nagumo, Ohara & Jaranilla-Sanchez (2026), *Journal of Disaster Research* 21(2): the swamp's role in storing floodwaters
        - Key Biodiversity Areas factsheet, Candaba Swamp: wet-season flooding, dry-season rice and watermelon, fishponds
        - [SESAM field report, UP Los Baños](https://sesam.uplb.edu.ph/?p=785): duck raising
        - [DA eyes Candaba Swamp waterway project to curb flooding](https://www.gmanetwork.com/news/topstories/regions/1001490/da-eyes-candaba-swamp-waterway-project-to-curb-flooding/story/) — GMA News
        - [Candaba Swamp](https://en.wikipedia.org/wiki/Candaba_Swamp) — Wikipedia
        - [The amazing farmer-fishermen of Candaba](https://www.sunstar.com.ph/article/1943787/pampanga/opinion/tantingco-the-amazing-farmer-fishermen-of-candaba) — SunStar Pampanga (opinion)

        **Impact on farmers**
        - [Pampanga agri damage climbs to ₱917.6M](https://www.sunstar.com.ph/pampanga/pampanga-agri-damage-climbs-to-p9176-m) — SunStar Pampanga
        - [PCIC allocates ₱187 million for post-typhoon farmer insurance payouts](https://context.ph/2026/09/06/pcic-allocates-p187-million-for-post-typhoon-farmer-insurance-payouts/) — Context.ph

        **Photos of Candaba**
""" + "\n".join(f"        - [Photo {i + 1}]({p['url']}) — {p['source']}" for i, p in enumerate(CANDABA_PHOTOS)))

# ── Page: Flood Map ───────────────────────────────────────────────────────────
def page_flood_map():
    st.title(":material/map: Interactive Flood Map")

    date_options  = df_flood["Date"].dt.strftime("%Y-%m-%d").tolist()
    selected_date = st.select_slider(
        "Select scene date:", options=date_options,
        value=f"{PEAK_ROW['Date']:%Y-%m-%d}",
        format_func=lambda d: f"{fmt_date(d.replace('-', ''))}"
    )
    date_nodash = selected_date.replace("-", "")
    if selected_date in BASELINE_DATES:
        st.info("This is a pre-flood baseline scene. Flood is measured as change against it, so it reads 0 Ha.", icon=":material/info:")
    elif selected_date == CHECK_DATE:
        st.info(f"This is the false-alarm check, before any storm. The {FALSE_ALARM_HA:,.0f} Ha flagged here is "
                "the method's error margin, not a real flood.", icon=":material/info:")

    sel = df_flood[df_flood["Date"].dt.strftime("%Y-%m-%d") == selected_date].iloc[0]
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Open Storm Flood", f"{sel['Open Storm Flood (Ha)']:,.0f} Ha")
    c2.metric("Hidden Flood",     f"{sel['Hidden Flood (Ha)']:,.0f} Ha")
    c3.metric("Flooded Cropland", f"{sel['Flooded Cropland (Ha)']:,.0f} Ha")
    c4.metric("Total Open Water", f"{sel['Total Open Water (Ha)']:,.0f} Ha",
              help="All open water on this date, including the usual river, ponds and swamp water")

    t1, t2 = st.columns(2)
    show_flood = t1.checkbox(":material/water: Show flood map for this date", value=True,
                             help="Storm flood, hidden flood and normal water, classified from NISAR for the selected date")
    show_sar   = t2.checkbox(":material/satellite_alt: Show SAR RGB composite", value=False,
                             help="The raw radar image the flood map was classified from")

    m = folium.Map(location=CENTER, zoom_start=12, tiles=None)

    folium.TileLayer(
        tiles="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png",
        attr='© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors © <a href="https://carto.com/attributions">CARTO</a>',
        name="Dark Basemap", subdomains="abcd", max_zoom=20
    ).add_to(m)
    folium.TileLayer(
        tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
        attr="Tiles © Esri — Source: Esri, Maxar, Earthstar Geographics",
        name="Optical Satellite (Esri)"
    ).add_to(m)

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

    if show_sar:
        tif_path = os.path.join(TIFS_DIR, f"{date_nodash}_SAR_RGB_composite.tif")
        if os.path.exists(tif_path):
            with st.spinner("Loading SAR imagery…"):
                img_b64 = tif_to_png_base64(tif_path)
            if img_b64:
                folium.raster_layers.ImageOverlay(
                    image=f"data:image/png;base64,{img_b64}",
                    bounds=BOUNDS, opacity=0.65,
                    name=f"{layer_swatch('linear-gradient(135deg,#3110a0,#bd53ff,#bda981)')}NISAR SAR Composite · {fmt_date(date_nodash)}",
                    interactive=True
                ).add_to(m)
        else:
            st.warning(f"No SAR composite found for {selected_date}", icon=":material/warning:")

    if show_flood:
        mask_path = os.path.join(TIFS_DIR, f"{date_nodash}_flood_thematic_mask.tif")
        if os.path.exists(mask_path):
            with st.spinner("Loading flood map…"):
                fm_b64 = classes_to_png_base64(mask_path, {k: c for k, (c, _) in THEMATIC_CLASSES.items()})
            if fm_b64:
                folium.raster_layers.ImageOverlay(
                    image=f"data:image/png;base64,{fm_b64}",
                    bounds=BOUNDS, opacity=0.8,
                    name=f"{layer_swatch('rgb(33,150,243)')}Flood Map · {fmt_date(date_nodash)}",
                    interactive=True
                ).add_to(m)
            else:
                st.warning("Could not render the flood map for this date", icon=":material/warning:")
        else:
            st.warning(f"No flood map found for {selected_date}", icon=":material/warning:")

    overlay_options = {
        "At-Risk Cropland":        ("agricultural_cropland_at_risk_overlay.tif", (244, 67, 54)),
        "Cropland (ESA WorldCover)": ("cropland_worldcover.tif",                (139, 195, 74)),
        "Usual Water (JRC)":       ("normal_water.tif",                          (0, 188, 212)),
    }
    selected_overlay = st.selectbox(
        "Add a season-wide layer:",
        ["None"] + list(overlay_options.keys()) + ["Flood Duration"],
        help="These layers summarise the whole season and do not change with the date slider. "
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
                    bounds=BOUNDS, opacity=0.8,
                    name=f"{layer_swatch('linear-gradient(90deg,#ffffb2,#fd8d3c,#800026)')}Flood Duration",
                    interactive=True
                ).add_to(m)
            else:
                st.warning("Could not render Flood Duration overlay", icon=":material/warning:")
        else:
            st.warning("Overlay file not found: consecutive_flood_duration.tif", icon=":material/warning:")
    elif selected_overlay != "None":
        overlay_file, overlay_color = overlay_options[selected_overlay]
        overlay_path = os.path.join(TIFS_DIR, overlay_file)
        if os.path.exists(overlay_path):
            with st.spinner("Loading overlay…"):
                ov_b64 = mask_to_png_base64(overlay_path, overlay_color)
            if ov_b64:
                folium.raster_layers.ImageOverlay(
                    image=f"data:image/png;base64,{ov_b64}",
                    bounds=BOUNDS, opacity=0.6,
                    name=f"{layer_swatch(f'rgb{overlay_color}')}{selected_overlay}",
                    interactive=True
                ).add_to(m)
            else:
                st.warning(f"Could not render {selected_overlay} overlay", icon=":material/warning:")
        else:
            st.warning(f"Overlay file not found: {overlay_file}", icon=":material/warning:")

    aoi_layer = folium.FeatureGroup(name=f"{layer_swatch('transparent', border='2px solid cyan')}NISAR Study Area")
    folium.Rectangle(
        bounds=BOUNDS,
        color="cyan", fill=False, weight=2,
        tooltip="Study area — Candaba Floodplain (cut from NISAR track 140A, frame 9)"
    ).add_to(aoi_layer)
    aoi_layer.add_to(m)

    mun_coords = {
        "Candaba":  [15.09, 120.83],
        "Arayat":   [15.15, 120.76],
        "San Luis": [15.04, 120.79],
        "Cabiao":   [15.24, 120.84],
        "Apalit":   [14.95, 120.76],
    }
    mun_layer = folium.FeatureGroup(name=f"{layer_swatch('orange', round_=True)}Key Municipalities")
    for mun, coords in mun_coords.items():
        row = df_mun[df_mun["Municipality"] == mun]
        if not row.empty:
            risk  = row[RISK_COL].values[0]
            flood = row[PEAK_MUN_COL].values[0]
            folium.CircleMarker(
                coords, radius=9, color="orange",
                fill=True, fill_opacity=0.8,
                tooltip=f"<b>{mun}</b><br>At-Risk Cropland: {risk:,.0f} Ha"
                        f"<br>Flood on {fmt_date(META['peak_storm_flood_date'])}: {flood:,.0f} Ha"
            ).add_to(mun_layer)
    mun_layer.add_to(m)

    folium.LayerControl(collapsed=True).add_to(m)
    m.fit_bounds(BOUNDS, padding=(10, 10))

    map_col, legend_col = st.columns([3, 1])
    with map_col:
        st_folium(m, height=580, use_container_width=True, returned_objects=[])
        role = ROLE_LABELS[sel["Role"]].lower()
        shown = [name for name, on in [("flood map", show_flood), ("SAR image", show_sar)] if on]
        if shown:
            st.caption(
                f":material/calendar_month: Showing the NISAR {' and '.join(shown)} for **{fmt_date(date_nodash)}, {selected_date[:4]}** "
                f"({role} scene). Move the date slider above to see another pass."
            )
    with legend_col:
        if show_flood:
            st.markdown(legend_html(
                [(f"rgb{c}", label) for c, label in THEMATIC_CLASSES.values()],
                title="FLOOD MAP"
            ), unsafe_allow_html=True)
        if show_sar:
            st.markdown(legend_html(
                [(c, f"<b>{name}</b> = {desc}") for c, name, desc in SAR_RGB_CHANNELS],
                title="SAR RGB COMPOSITE"
            ), unsafe_allow_html=True)
            st.markdown(legend_html(
                [("rgb(49,16,133)",   "Dark indigo = open water (radar reflects away)"),
                 ("rgb(189,83,255)",  "Bright violet-pink = water under vegetation (double-bounce)"),
                 ("rgb(145,96,163)",  "Dusty mauve = dry cropland"),
                 ("rgb(189,169,129)", "Tan = trees, towns and other land")],
                title="HOW TO READ THE COLOURS"
            ), unsafe_allow_html=True)
        if selected_overlay == "Flood Duration":
            st.markdown(legend_html(
                [(f"rgb{c}", duration_label(n)) for n, c in DURATION_COLORS.items()],
                title="CONSECUTIVE FLOODED PASSES"
            ), unsafe_allow_html=True)
        elif selected_overlay != "None":
            label = {
                "At-Risk Cropland": f"Cropland under water {RISK_DAYS}+ days: high risk of crop loss, not confirmed damage",
                "Cropland (ESA WorldCover)": "Cropland (ESA WorldCover 2021)",
                "Usual Water (JRC)": f"Water ≥ {META['jrc_usual_water_min_pct']}% of the time (JRC 1984–2021)",
            }[selected_overlay]
            st.markdown(legend_html(
                [(f"rgb{overlay_options[selected_overlay][1]}", label)],
                title="SEASON-WIDE LAYER"
            ), unsafe_allow_html=True)
        st.markdown(legend_html(
            [("orange", "Key municipality (hover for stats)"),
             ("outline:cyan", "NISAR study area (cyan box)")],
            title="MAP FEATURES"
        ), unsafe_allow_html=True)

    st.markdown("---")
    st.subheader(":material/compare: Before vs. after")
    st.caption("Drag the handle to compare the pre-flood baseline with any later scene. "
               "Flood map colours: grey-blue = normal water, blue = storm flood, orange = hidden flood, dark grey = land.")
    cmp1, cmp2, cmp3 = st.columns([2, 2, 1])
    before_date = cmp1.selectbox("Before", date_options, index=date_options.index(BASELINE_DATES[-1]),
                                 format_func=lambda d: f"{fmt_date(d.replace('-', ''))} ({ROLE_LABELS[df_flood.loc[df_flood['Date'] == d, 'Role'].iloc[0]].lower()})")
    after_date  = cmp2.selectbox("After",  date_options, index=date_options.index(f"{PEAK_ROW['Date']:%Y-%m-%d}"),
                                 format_func=lambda d: f"{fmt_date(d.replace('-', ''))} ({ROLE_LABELS[df_flood.loc[df_flood['Date'] == d, 'Role'].iloc[0]].lower()})")
    cmp_view    = cmp3.radio("Show", ["Flood map", "SAR image"], horizontal=False)

    def comparison_image(date_str):
        stem = date_str.replace("-", "")
        if cmp_view == "SAR image":
            return tif_to_png_base64(os.path.join(TIFS_DIR, f"{stem}_SAR_RGB_composite.tif"), max_width=1000)
        return classes_to_png_base64(os.path.join(TIFS_DIR, f"{stem}_flood_thematic_mask.tif"),
                                     {0: (48, 48, 52), **{k: c for k, (c, _) in THEMATIC_CLASSES.items()}})

    before_b64, after_b64 = comparison_image(before_date), comparison_image(after_date)
    if before_b64 and after_b64:
        st.iframe(f"""
        <div id="cmp" style="position:relative;max-width:680px;margin:auto;user-select:none;background:#1e1e1e;border-radius:8px;">
          <img src="data:image/png;base64,{after_b64}" style="width:100%;display:block;border-radius:8px;">
          <div id="clip" style="position:absolute;top:0;left:0;height:100%;width:50%;overflow:hidden;border-radius:8px 0 0 8px;background:#1e1e1e;">
            <img src="data:image/png;base64,{before_b64}" id="bimg" style="display:block;height:100%;max-width:none;">
          </div>
          <div id="bar" style="position:absolute;top:0;left:50%;height:100%;width:3px;background:#00bcd4;transform:translateX(-50%);"></div>
          <span style="position:absolute;top:8px;left:8px;background:rgba(0,0,0,.65);color:#fff;padding:2px 8px;border-radius:4px;font:13px sans-serif;">Before · {fmt_date(before_date.replace('-', ''))}</span>
          <span style="position:absolute;top:8px;right:8px;background:rgba(0,0,0,.65);color:#fff;padding:2px 8px;border-radius:4px;font:13px sans-serif;">After · {fmt_date(after_date.replace('-', ''))}</span>
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
        st.warning("Could not load one of the selected scenes.", icon=":material/warning:")

# ── Page: Timeline ────────────────────────────────────────────────────────────
def page_timeline():
    st.title(":material/timeline: Flood Timeline (Jun to Oct 2026)")
    st.markdown(f"Tracking the full monsoon and typhoon season across {len(df_flood)} NISAR passes.")

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df_flood["Date"], y=df_flood["Open Storm Flood (Ha)"],
        name="Open Storm Flood", fill="tozeroy",
        line=dict(color="#2196F3", width=2)
    ))
    fig.add_trace(go.Scatter(
        x=df_flood["Date"], y=df_flood["Hidden Flood (Ha)"],
        name="Hidden Flood (experimental)", fill="tozeroy",
        line=dict(color="#FF9800", width=2)
    ))
    fig.add_trace(go.Scatter(
        x=df_flood["Date"], y=df_flood["Flooded Cropland (Ha)"],
        name="Flooded Cropland",
        line=dict(color="#F44336", width=3, dash="dot")
    ))

    fig.add_hline(
        y=FALSE_ALARM_HA, line=dict(color="#90A4AE", width=1, dash="dot"),
        annotation_text=f"Storm-flood error margin ({FALSE_ALARM_HA:,.0f} Ha, {fmt_date(META['check_date'])} false-alarm check)",
        annotation_position="bottom right", annotation_font=dict(size=10, color="#B0BEC5")
    )
    fig.add_vrect(
        x0="2026-07-02", x1="2026-07-20",
        fillcolor="#4CAF50", opacity=0.12,
        annotation_text="Pre-flood baseline",
        annotation_position="top left"
    )
    fig.add_vrect(
        x0="2026-07-27", x1="2026-08-10",
        fillcolor="gray", opacity=0.2,
        annotation_text="NISAR outage",
        annotation_position="top left"
    )
    storm_events = [
        ("2026-08-03", "TD Luis landfall"),
        ("2026-08-05", "Maymay: tropical storm"),
        ("2026-08-19", "TD Neneng"),
        ("2026-09-20", "80+ barangays<br>still flooded"),
    ]
    for i, (when, label) in enumerate(storm_events):
        fig.add_shape(type="line", x0=when, x1=when, y0=0, y1=1, yref="paper",
                      line=dict(color="#B39DDB", width=1, dash="dash"))
        fig.add_annotation(x=when, y=0.62 - 0.12 * (i % 2), yref="paper", text=label,
                           showarrow=False, font=dict(size=10, color="#D1C4E9"),
                           bgcolor="rgba(0,0,0,0.5)", xanchor="left", xshift=4)

    fig.add_annotation(
        x=PEAK_ROW["Date"], y=PEAK_ROW["Open Storm Flood (Ha)"],
        text=f"Peak: {PEAK_ROW['Open Storm Flood (Ha)']:,.0f} ± {ERROR_MARGIN_HA:,.0f} Ha<br>{fmt_date(PEAK_ROW['Date'])} pass"
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
        f"{fmt_date(META['baseline_dates'][0])} and {fmt_date(META['baseline_dates'][1])} are the pre-flood baseline "
        f"scenes, so they read 0 Ha by design. {fmt_date(META['check_date'])} is a pre-storm false-alarm check: anything the "
        f"method flags there is error — {FALSE_ALARM_HA:,.0f} Ha for storm flood (dotted line) and "
        f"{CHECK_ROW['Hidden Flood (Ha)']:,.0f} Ha for hidden flood. Values near those levels are not a confident flood signal. "
        f"Storm flood only counts open water outside the usual-water footprint "
        f"({META['normal_water_ha']:,.0f} Ha, JRC Global Surface Water). Hidden flood: {HIDDEN_NOTE}"
    )

    st.subheader("Data Table")
    st.markdown(
        f"The numbers behind the chart above. **Each row is one NISAR pass** over the study area, and each column is an area "
        f"in hectares (1 Ha = 10,000 m², about the size of a football field) measured from that pass. "
        f"**Highlighted cells** mark the highest value in each column. Hover over a column name for its definition."
    )
    table = df_flood.assign(
        Date=df_flood["Date"].map(lambda d: f"{fmt_date(d)}, {d.year}"),
        Role=df_flood["Role"].map(ROLE_LABELS)
    ).set_index("Date")
    numeric_cols = table.select_dtypes("number").columns
    st.dataframe(
        table.style.highlight_max(subset=numeric_cols, color="#1a4a7a").format("{:,.0f}", subset=numeric_cols),
        width="stretch",
        column_config={
            "Date": st.column_config.TextColumn(
                "Date", help="Date of the NISAR pass (UTC). The Aug 10 pass was about 5:30 AM on Aug 11, Manila time."),
            "Role": st.column_config.TextColumn(
                "Role", help=f"False-alarm check = before any storm, used to measure error. "
                             f"Pre-flood baseline = reference scenes later passes are compared against. "
                             f"Post-storm = passes after the August storms."),
            "Total Open Water (Ha)": st.column_config.NumberColumn(
                "Total Open Water (Ha)", help="All open water seen on this pass, including the usual river, "
                                              "fishponds and swamp water."),
            "Open Storm Flood (Ha)": st.column_config.NumberColumn(
                "Open Storm Flood (Ha)", help="Open water outside the usual-water footprint (JRC): "
                                              "new flooding caused by the storms."),
            "Hidden Flood (Ha)": st.column_config.NumberColumn(
                "Hidden Flood (Ha)", help=f"Experimental: {HIDDEN_RULE} Not validated."),
            "Flooded Cropland (Ha)": st.column_config.NumberColumn(
                "Flooded Cropland (Ha)", help="Storm or hidden flood that falls on cropland (ESA WorldCover)."),
        }
    )
    with st.expander(":material/help: What do the columns mean?"):
        st.markdown(f"""
        | Column | Meaning |
        |---|---|
        | **Role** | *False-alarm check* ({fmt_date(META['check_date'])}): before any storm, so anything flagged is error. *Pre-flood baseline*: the reference scenes, so flood reads 0. *Post-storm*: passes after the August storms. |
        | **Total Open Water** | All open water on that pass, including the usual river, fishponds and swamp water. |
        | **Open Storm Flood** | Open water outside the usual-water footprint ({META['normal_water_ha']:,.0f} Ha, JRC): the new flooding. |
        | **Hidden Flood** | *Experimental:* {HIDDEN_RULE} {HIDDEN_NOTE} |
        | **Flooded Cropland** | Storm or hidden flood that falls on cropland (ESA WorldCover). |

        **How to read it:** storm flood jumps from 0 to {PEAK_ROW['Open Storm Flood (Ha)']:,.0f} Ha between the July baseline
        and {fmt_date(PEAK_ROW['Date'])}, then drains slowly to {LAST_ROW['Open Storm Flood (Ha)']:,.0f} Ha by
        {fmt_date(LAST_ROW['Date'])}. Values close to the {fmt_date(META['check_date'])} false-alarm row are within the error margin.
        """)

# ── Page: Agricultural Impact ─────────────────────────────────────────────────
def page_agriculture():
    st.title(":material/agriculture: Agricultural Impact by Municipality")
    st.markdown(f"**At-risk cropland** = cropland (ESA WorldCover) flooded on **{RISK_PASSES}+ consecutive NISAR passes**, "
                f"i.e. under water for **{RISK_DAYS}+ days**: **high risk of crop loss, not confirmed damage**. "
                f"Shown as a range from the strict ({THR_STRICT:g} dB) to the standard ({THR:g} dB) threshold: "
                f"**{TOTAL_AT_RISK_STRICT:,.0f}–{TOTAL_AT_RISK:,.0f} Ha** across the study area.")
    st.caption("In the wet season much of the swamp interior is fishponds or fallow land, so at-risk cropland there is "
               "not all rice.")

    top_n  = st.slider("Show top N municipalities", 5, 20, 10)
    df_top = df_mun.head(top_n)

    fig = px.bar(
        df_top,
        x=RISK_COL,
        y="Municipality",
        orientation="h",
        color="Province",
        hover_data=["Cropland (Ha)", PEAK_MUN_COL, RISK_COL_STRICT],
        labels=DISPLAY_COLS,
        title=f"Top {top_n} Municipalities by At-Risk Cropland",
        template="plotly_dark",
        color_discrete_sequence=px.colors.qualitative.Bold
    )
    fig.update_layout(height=520, yaxis=dict(autorange="reversed"))
    st.plotly_chart(fig, width="stretch")

    top_mun = df_mun.iloc[0]
    k1, k2, k3, k4 = st.columns([1, 1.6, 0.9, 0.9])
    k1.metric("Most affected", top_mun["Municipality"], delta=top_mun["Province"],
              delta_color="off", delta_arrow="off", border=True, icon=":material/location_on:")
    k2.metric(f"{top_mun['Municipality']} cropland at high risk",
              f"{top_mun[RISK_COL_STRICT]:,.0f}–{top_mun[RISK_COL]:,.0f} Ha",
              delta=f"up to {top_mun[RISK_COL] / top_mun['Cropland (Ha)'] * 100:.0f}% of its cropland",
              delta_color="inverse", delta_arrow="off", border=True, icon=":material/agriculture:",
              help=f"Range = {THR_STRICT:g} dB (strict) to {THR:g} dB (standard) threshold. High risk of crop loss, "
                   "not confirmed damage.")
    k3.metric("Municipalities", f"{len(df_mun)}", delta="in the study area",
              delta_color="off", delta_arrow="off", border=True, icon=":material/location_city:")
    k4.metric("Provinces", f"{len(PROVINCES)}", delta="Central Luzon",
              delta_color="off", delta_arrow="off", border=True, icon=":material/map:")

    counts = df_mun["Province"].value_counts()
    st.markdown(
        '<div style="margin:2px 0 8px;font-size:13px;opacity:0.85;">Municipalities per province: '
        + "".join(f'<span style="display:inline-block;padding:3px 10px;margin:3px 4px;border-radius:999px;'
                  f'background:rgba(138,180,248,0.12);border:1px solid rgba(138,180,248,0.25);color:#cfe0ff;">'
                  f'{prov} · {n}</span>' for prov, n in counts.items())
        + "</div>",
        unsafe_allow_html=True
    )

    st.subheader(f"Threshold sensitivity: {THR:g} dB vs {THR_STRICT:g} dB")
    st.caption(
        "A pixel counts as open water when its radar backscatter falls below the threshold. "
        f"{THR:g} dB is our standard cut-off; {THR_STRICT:g} dB is stricter and only keeps the most confident water pixels. "
        "Municipalities whose numbers barely change are robust; big drops mean the estimate is less certain there."
    )
    sens = df_sens.copy()
    sens["Metric"] = sens["Metric"].str.replace(
        r"\b(\d{8})\b", lambda mt: f"{fmt_date(mt.group(1))}", regex=True)
    st.dataframe(
        sens.set_index("Metric").style.format("{:,.1f}"),
        width="stretch"
    )
    fig2 = go.Figure()
    fig2.add_trace(go.Bar(
        name=f"@ {THR:g} dB (standard)",
        x=df_top["Municipality"],
        y=df_top[RISK_COL],
        marker_color="#2196F3"
    ))
    fig2.add_trace(go.Bar(
        name=f"@ {THR_STRICT:g} dB (strict)",
        x=df_top["Municipality"],
        y=df_top[RISK_COL_STRICT],
        marker_color="#FF9800"
    ))
    fig2.update_layout(
        barmode="group", template="plotly_dark",
        xaxis_title="Municipality", yaxis_title="At-Risk Cropland (Ha)",
        height=380
    )
    st.plotly_chart(fig2, width="stretch")

    st.subheader("Full municipality table")
    st.dataframe(df_mun.rename(columns=DISPLAY_COLS), width="stretch", hide_index=True)
    st.caption(
        f"Municipal at-risk totals sum to {df_mun[RISK_COL].sum():,.0f} Ha, matching the basin-wide total. "
        f"Peak flood per municipality includes both storm and hidden flood on {fmt_date(META['peak_storm_flood_date'])}. "
        "Boundaries: geoBoundaries PHL ADM3."
    )

# ── Page: Science & Data ─────────────────────────────────────────────────────────
def page_sar_science():
    st.title(":material/radar: Science & Data — How NISAR Sees the Flood")

    st.markdown("""
    ### Why L-band SAR detects floods — even under crops
    - NISAR sends out its own microwave pulses and listens for the echo (**backscatter**), so it works
      day or night and straight through typhoon clouds
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
    col1.info(f"**Backscatter < {THR:g} dB**\n\nDark = open water (mirror-like reflection away from the sensor)")
    col2.warning("**HH rises by more than 3 dB** vs. the pre-storm average\n\n"
                 "Bright = possible water hidden beneath vegetation (experimental)")
    col3.error("**HH rises more than 2 dB more than HV** (HH/HV ratio up)\n\n"
               "Double-bounce dominates. Only kept within about 500 m of open flood")

    with st.expander(":material/menu_book: Glossary — radar terms in plain language"):
        st.markdown(f"""
        | Term | What it means |
        |---|---|
        | **Backscatter** | How much of the radar pulse comes back to the satellite. |
        | **dB (decibel)** | A log scale for backscatter. More negative = darker = less echo. {THR:g} dB is quite dark. |
        | **HH** | Pulse sent and received **h**orizontally. Sensitive to double-bounce (flooded vegetation, buildings). |
        | **HV** | Sent **h**orizontal, received **v**ertical. Sensitive to messy "volume" scattering in leaves and branches. |
        | **HHHH / HVHV** | How NISAR's GCOV product names the HH and HV power layers. |
        | **Double-bounce** | Pulse hits water, then a stem (or wall), then returns — a strong, bright echo. |
        | **Hidden flood** | *Experimental:* {HIDDEN_RULE} Not validated. |
        | **Speckle / Lee filter** | Radar images are naturally grainy ("speckle"); the Lee filter smooths it while keeping edges. |
        | **Otsu threshold** | An automatic way to pick a brightness cut-off between two groups. We use it only as a cross-check ({META['otsu_reference_db']} dB). |
        | **Baseline scene** | A pre-flood image ({fmt_date(META['baseline_dates'][0])}, {fmt_date(META['baseline_dates'][1])}) that later scenes are compared against. |
        | **False-alarm check** | A scene before any storm ({fmt_date(META['check_date'])}). Whatever the method flags there is error, which gives our error margin. |
        | **Usual water** | Places that were water at least {META['jrc_usual_water_min_pct']}% of the time in 1984–2021 (JRC Global Surface Water). Excluded from storm flood. |
        """)

    st.markdown("---")
    st.markdown(f"""
    ### Processing pipeline used in this project
    1. **Download** — NISAR L2 GCOV HDF5 via ASF Earthdata ({len(df_flood)} scenes, Track 140A)
    2. **Crop** — Extract Candaba AOI from each ~5 GB scene → ~40 MB
    3. **Despeckle** — Lee filter (5×5 window) to reduce radar speckle noise
    4. **Convert** — Linear power → decibels (dB scale)
    5. **Reproject** — Native UTM → WGS84 (EPSG:4326) for mapping
    6. **Classify** — Open water below a fixed **{THR:g} dB** threshold (Otsu, {META['otsu_reference_db']} dB, as a cross-check).
       Water inside the JRC usual-water footprint = normal water; outside it = **storm flood**
    7. **Hidden flood (experimental)** — compared with the average of the {fmt_date(META['baseline_dates'][0])} and
       {fmt_date(META['baseline_dates'][1])} baselines: HH rose by more than 3 dB, the HH rise exceeds the HV rise by more than
       2 dB, the pixel is not open or normal water, and it has valid data on all three dates. A 3×3 cleanup removes isolated
       pixels, and only pixels within about 500 m of same-date storm flood are kept. Not calculated for the baseline dates
    8. **Assess risk** — ESA WorldCover cropland flooded on {RISK_PASSES}+ consecutive passes = **at-risk cropland**
    9. **Measure** — Area statistics per municipality (geoBoundaries ADM3)
    10. **Validate** — {fmt_date(META['check_date'])} false-alarm check for an error margin, plus a {THR_STRICT:g} dB sensitivity run

    ### Sensor specs
    | Parameter | Value |
    |---|---|
    | Satellite | NISAR (NASA / ISRO) |
    | Band | L-band (24 cm wavelength) |
    | Polarizations | HH, HV (GCOV layers HHHH, HVHV) |
    | Repeat cycle | 12 days |
    | Track | 140 Ascending, Frame 9 |
    | Processing | PROVISIONAL V1 (CRID P05023) |

    ### Data sources
    """ + "\n".join(f"    - {s}" for s in META["data_sources"]) + """

    ### Resources
    - [NISAR Data User Guide](https://nisar-docs.asf.alaska.edu/)
    - [ASF Data Search Vertex](https://search.asf.alaska.edu/)
    - [NISAR Applications — Societal Benefits](https://nisar.jpl.nasa.gov/applications/societal-benefit/)
    - [ESA WorldCover](https://esa-worldcover.org/)
    - [JRC Global Surface Water](https://global-surface-water.appspot.com/)
    - [geoBoundaries](https://www.geoboundaries.org/)
    - [CSA SAR Python Tutorial](https://github.com/asc-csa/Synthetic_Aperture_Radar_Tutorial)
    """)

    st.markdown("---")
    render_code_and_data()

# ── Page: About ───────────────────────────────────────────────────────────────
def page_about():
    st.title(":material/groups: About Signal to Noise")
    st.markdown("""
    We are **Signal to Noise**, a team taking part in the **NASA Space Apps Challenge 2026**
    (*Dancing with the SARs*). We used NISAR radar to follow the 2026 flood season in the Candaba Floodplain
    and turn it into maps and numbers that farmers, local governments and the public can use.
    """)

    st.subheader("The team")
    cols = st.columns(len(TEAM_MEMBERS))
    for i, (col, member) in enumerate(zip(cols, TEAM_MEMBERS)):
        with col:
            with st.container(border=True):
                st.markdown(
                    f'<div style="display:flex;flex-direction:column;align-items:center;text-align:center;gap:8px;'
                    f'padding:8px 0;">{avatar_html(member, i)}'
                    f'<div style="font-size:18px;font-weight:700;">{member["name"]}</div>'
                    f'<div style="font-size:13px;opacity:0.75;">{member["role"]}</div></div>',
                    unsafe_allow_html=True
                )
                link_cols = st.columns(len(member["links"]))
                for lc, (label, url) in zip(link_cols, member["links"].items()):
                    placeholder = not url or "your-" in url
                    lc.link_button(label, url or "https://example.com", icon=SOCIAL_ICONS.get(label, ":material/link:"),
                                   disabled=placeholder, width="stretch",
                                   help="Link coming soon" if placeholder else None)

    st.markdown("---")
    st.caption(":material/balance: Code released under the MIT License. NASA does not endorse this project. "
               "NISAR data courtesy of NASA/JPL-Caltech and ISRO, distributed by the Alaska Satellite Facility.")

def render_code_and_data():
    """Colab and GitHub links (shown on the Science & Data page)."""
    st.subheader(":material/science: Get our code & data")
    st.markdown(
        "Everything behind this app is open. The **Colab notebook** has the full preprocessing code, "
        "and the **GitHub repository** has this app and the processed data it uses."
    )
    b1, b2 = st.columns(2)
    for col, key, label, icon, help_text in [
        (b1, "colab",  "Open the Colab notebook", ":material/code_blocks:",
         "Download, crop, despeckle, classify and measure — runs in the browser"),
        (b2, "github", "View on GitHub", ":material/terminal:",
         "This Streamlit app and its data, MIT licensed"),
    ]:
        with col:
            with st.container(border=True):
                url = PROJECT_LINKS.get(key)
                st.link_button(label if url else f"{label} (coming soon)", url or "https://example.com",
                               icon=icon, disabled=not url, width="stretch", type="primary" if url else "secondary")
                st.caption(help_text)
    st.caption("Raw NISAR scenes are not included; download them from ASF Vertex (Track 140A, Frame 9).")

# ── Navigation ────────────────────────────────────────────────────────────────
PAGES = [
    st.Page(page_overview,    title="Overview",            icon=":material/home:", default=True),
    st.Page(page_flood_map,   title="Flood Map",           icon=":material/map:"),
    st.Page(page_timeline,    title="Timeline",            icon=":material/timeline:"),
    st.Page(page_agriculture, title="Agricultural Impact", icon=":material/agriculture:"),
    st.Page(page_sar_science, title="Science & Data",      icon=":material/radar:"),
    st.Page(page_about,       title="About the Team",      icon=":material/groups:"),
]
current_page = st.navigation(PAGES, position="hidden")

st.markdown("""
<style>
[data-testid="stSidebarUserContent"] { padding-top: 0.5rem; padding-bottom: 1rem; }
[data-testid="stSidebar"] [data-testid="stVerticalBlock"] { gap: 0.3rem; }
[data-testid="stSidebar"] .stMarkdown,
[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] { margin-bottom: 0 !important; }
[data-testid="stSidebar"] [data-testid="stElementContainer"]:has([data-testid="stPageLink"]),
[data-testid="stSidebar"] [data-testid="stPageLink"],
[data-testid="stSidebar"] [data-testid="stPageLink"] [data-testid="stTooltipHoverTarget"] {
    height: auto !important;
    min-height: 0 !important;
    overflow: visible !important;
}
[data-testid="stSidebar"] [data-testid="stElementContainer"]:has([data-testid="stPageLink"]) {
    margin: 1px 0 !important;
}
[data-testid="stSidebar"] [data-testid="stPageLink-NavLink"] {
    box-sizing: border-box;
    min-height: 44px;
    padding: 0.6rem 0.85rem !important;
    margin: 2px 0 !important;
    gap: 0.7rem;
    border-radius: 10px;
    transition: background-color 0.15s ease;
}
[data-testid="stSidebar"] [data-testid="stPageLink-NavLink"]:hover {
    background-color: rgba(0, 188, 212, 0.14);
}
[data-testid="stSidebar"] [data-testid="stPageLink"] p { font-size: 15px; }
[data-testid="stSidebar"] .name { font-size: 18px; font-weight: 700; line-height: 1.1; }
[data-testid="stSidebar"] .tag  { font-size: 12px; opacity: 0.7; }
.sidebar-label { font-size: 11px; letter-spacing: 1px; color: #8ab4f8; font-weight: 600;
                 margin: 18px 0 6px 2px; line-height: 1.2; }
</style>
""", unsafe_allow_html=True)

with st.sidebar:
    logo_src = logo_base64(LOGO_PATH)
    brand = (f'<img src="{logo_src}" alt="Signal to Noise" style="width:105px;display:block;margin:0 0 8px 2px;">'
             if logo_src else '<div class="name">Signal to Noise</div>')
    st.markdown(f"""
    <div style="margin:4px 0 2px;">{brand}<div class="tag">Dancing with the SARs · NASA Space Apps 2026</div></div>
    <div class="sidebar-label">NAVIGATE</div>
    """, unsafe_allow_html=True)
    for p in PAGES[:-1]:
        st.page_link(p)
    st.markdown(
        '<div class="sidebar-label">TEAM</div><div style="display:flex;align-items:center;margin:2px 0 6px;">'
        + "".join(f'<div style="margin-left:{0 if i == 0 else -10}px;">'
                  f'{avatar_html(m, i, size=34, ring="#0e1117")}</div>' for i, m in enumerate(TEAM_MEMBERS))
        + '<span style="margin-left:10px;font-size:13px;opacity:0.8;">Signal to Noise</span></div>',
        unsafe_allow_html=True
    )
    st.page_link(PAGES[-1], label="About the team")

current_page.run()
