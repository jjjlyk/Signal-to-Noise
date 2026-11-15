# Signal to Noise — Dancing with the SARs

**NASA Space Apps Challenge 2026 · Challenge: *Dancing with the SARs***

An interactive Streamlit app that uses **NISAR** (NASA–ISRO Synthetic Aperture Radar) L-band data to track how the
**Candaba Floodplain** in Central Luzon, Philippines floods and drains across the 2026 monsoon and typhoon season,
and what that means for the rice farms that surround it.

## Why Candaba?

Candaba is one of the Philippines' largest freshwater wetlands and a major rice-growing basin. It sits low, so when
the Pampanga River system overflows, water collects here for weeks. Optical satellites can't see through typhoon
clouds; NISAR's radar can, day or night, and its L-band signal even detects water **hidden beneath vegetation**.

In August 2026, the southwest monsoon and Tropical Depressions Luis and Maymay pushed the Pampanga River past critical
level. Candaba recorded the highest rice damage in the province, and parts of it were still flooded in late September.
NISAR's Aug 10 pass (about 5:30 AM on Aug 11, Manila time) caught the flood near its peak.

## What the app shows

| Page | What you can do |
|---|---|
| 🏠 **Overview** | Key numbers, flood extent per pass, what we learned, and future NISAR applications |
| 🗺️ **Flood Map** | Step through 9 NISAR scenes; toggle peak storm / hidden flood, at-risk cropland and flood-duration overlays; drag a before/after slider |
| 📊 **Timeline** | Open flood, hidden flood and flooded cropland over time, with the pre-flood baseline, storm events and data outage marked |
| 🌾 **Agricultural Impact** | At-risk cropland for 40 municipalities in 4 provinces, with a −14 dB vs −15 dB threshold sensitivity check |
| 📡 **SAR Science** | How radar sees open vs. hidden flood, a plain-language glossary, and our processing pipeline |

## Data

- **NISAR L2 GCOV** (HH and HV polarizations), Track 140 Ascending, Frame 9 — 9 scenes, Jun 23 to Oct 9, 2026,
  from the [ASF Data Search Vertex](https://search.asf.alaska.edu/) / NASA Earthdata
- Jul 5 and Jul 17 scenes serve as the **pre-flood baseline** for change detection
- SAR RGB composites: Red = HH, Green = HV, Blue = HH − HV (all in dB)
- Cropland mask and municipal boundaries used to compute per-municipality impact
- Basemaps: Stadia Maps / OpenStreetMap (dark) and Esri World Imagery (optical)

## Processing pipeline

1. Download NISAR L2 GCOV HDF5 scenes
2. Crop to the Candaba area of interest (120.65–121.05°E, 14.85–15.30°N)
3. Despeckle with a 5×5 Lee filter
4. Convert linear power to decibels
5. Reproject to WGS84 (EPSG:4326)
6. Classify open water, storm flood and hidden flood (Otsu threshold + change vs. baseline)
7. Compute area statistics per municipality

Outputs live in `data/` (CSV / JSON statistics) and `tifs/` (SAR RGB composites and flood overlays).

## Run it locally

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Project structure

```
app.py              Streamlit app
data/               Flood statistics, municipality rankings, study-area summary
tifs/               SAR RGB composites (one per date) and flood classification overlays
requirements.txt    Python dependencies
```

## License

[MIT](LICENSE)

*NASA does not endorse this project. NISAR data courtesy of NASA/JPL-Caltech and ISRO, distributed by the
Alaska Satellite Facility.*
