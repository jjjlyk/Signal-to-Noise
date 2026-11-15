<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="assets/logo/signal_to_noise_white_logo.png">
    <img src="assets/logo/signal_to_noise_black_logo.png" alt="Signal to Noise" width="260">
  </picture>
</p>

<h3 align="center">Dancing with the SARs · NASA Space Apps Challenge 2026</h3>

<p align="center">
  <a href="https://signal-to-noise.streamlit.app/"><img src="https://static.streamlit.io/badges/streamlit_badge_black_white.svg" alt="Open in Streamlit"></a>
  <a href="https://colab.research.google.com/drive/1zNbjOiFXpkCnQGa0v0q8sB_8D6jxiVPV?usp=sharing"><img src="https://colab.research.google.com/assets/colab-badge.svg" alt="Open in Colab"></a>
  <img src="https://img.shields.io/badge/built%20with-Streamlit-FF4B4B" alt="Built with Streamlit">
  <img src="https://img.shields.io/badge/data-NISAR%20L--band-00bcd4" alt="NISAR L-band">
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-blue" alt="MIT License"></a>
</p>

An interactive Streamlit app that uses **NISAR** (NASA–ISRO Synthetic Aperture Radar) L-band data to track how the
**Candaba Floodplain** in Central Luzon, Philippines floods and drains across the 2026 monsoon and typhoon season,
and what that means for the farms in and around it.

**Quick links:** [**Live app**](https://signal-to-noise.streamlit.app/) · [Preprocessing notebook (Colab)](https://colab.research.google.com/drive/1zNbjOiFXpkCnQGa0v0q8sB_8D6jxiVPV?usp=sharing) ·
[Run the app locally](#run-it-locally) · [Key results](#key-results) · [Team](#team)

---

## Why Candaba?

Candaba is a natural flood basin in Central Luzon that stores floodwaters from the Pampanga River system. Its extent
varies by definition and season. Most of it dries out from late November to April and becomes rice fields and watermelon
plantations. In the wet season it floods, and it is used for fishponds and duck raising.

In August 2026, the southwest monsoon (*habagat*), TD Luis (landfall Aug 3) and Maymay (a tropical storm by Aug 5) pushed
the Pampanga River past critical level. Candaba recorded the highest rice damage in the province, and parts of it were
still flooded in late September.

Optical satellites can't see through typhoon clouds. NISAR's radar can, day or night, and its L-band signal can even pick
up water beneath vegetation. NISAR's Aug 10 pass (about 5:30 AM on Aug 11, Manila time) caught the flood near its peak.

## What the app shows

| Page | What you can do |
|---|---|
| **Overview** | Key numbers, why Candaba (with photos), flood extent per pass with the error margin, what we learned, and future NISAR applications |
| **Flood Map** | Step through 9 dates and see where storm flood, hidden flood and normal water were on each one; add at-risk cropland, cropland, usual-water or flood-duration layers; drag a before/after slider |
| **Timeline** | Open flood, hidden flood and flooded cropland over time, with the pre-flood baseline, false-alarm error margin, storm events and data outage marked, plus the data table |
| **Agricultural Impact** | Cropland at high risk for 40 municipalities in 4 provinces, with a −14 dB vs −15 dB threshold sensitivity check |
| **Science & Data** | How radar sees open vs. hidden flood, a plain-language glossary, our processing pipeline, and links to our code |
| **About the Team** | The Signal to Noise team |

## Key results

- **Peak flood:** 18,832 ± ~1,500 ha of open storm flood on the Aug 10 pass. The margin comes from the Jun 23
  false-alarm check.
- **Slow drainage:** 4,923 ha was still flooded on Oct 9, two months later.
- **Cropland at high risk of crop loss:** 9,595–14,197 ha was flooded on 2+ consecutive passes (12+ days), at the
  −15 dB and −14 dB thresholds. Candaba alone: 2,820–4,445 ha. This is high risk, not confirmed damage: in the wet
  season much of the swamp interior is fishponds or fallow land.
- **False-alarm check:** 1,521 ha of storm flood and 62 ha of hidden flood were flagged on Jun 23, before any storm.
  Aug 10 storm flood was about 12 times the false-alarm level.
- **Hidden flood (experimental, not validated):** 833 ha on Aug 10. Because it is only searched for within about 500 m of
  open flood, its trend follows open flood and is not an independent result.

## Data

| Dataset | Used for |
|---|---|
| **NISAR L2 GCOV PROVISIONAL** (HH + HV), Track 140 Ascending, Frame 9 — 9 scenes, Jun 23 to Oct 9, 2026, from [ASF Vertex](https://search.asf.alaska.edu/) / NASA Earthdata | Flood detection |
| **ESA WorldCover 2021 v200** | Cropland |
| **JRC Global Surface Water occurrence v1.4 (2021)** | Usual water (≥25% occurrence), excluded from storm flood |
| **geoBoundaries PHL ADM2/ADM3** | Province and municipality boundaries |
| CARTO Dark Matter / OpenStreetMap and Esri World Imagery | Basemaps |

**Scene roles:** Jun 23 is a **false-alarm check** (before any storm). Jul 5 and Jul 17 are the **pre-flood baseline**.
Aug 10 to Oct 9 are **post-storm** scenes.

**SAR RGB composites:** Red = HH dB [−20, 0], Green = HV dB [−25, −5], Blue = HH − HV dB [2, 12]. Open water shows as
dark indigo, water under vegetation as bright violet-pink, dry cropland as dusty mauve, and other land as tan.

## Processing pipeline

The full code is in the [Colab notebook](https://colab.research.google.com/drive/1zNbjOiFXpkCnQGa0v0q8sB_8D6jxiVPV?usp=sharing).

1. Download NISAR L2 GCOV HDF5 scenes
2. Crop to the Candaba study area (120.65–121.05°E, 14.85–15.30°N)
3. Despeckle with a 5×5 Lee filter
4. Convert linear power to decibels
5. Reproject to WGS84 (EPSG:4326)
6. **Open water and storm flood:** open water is below a fixed −14 dB threshold (Otsu, −9.48 dB, as a cross-check).
   Water inside the JRC usual-water footprint is normal water; outside it is storm flood.
7. **Hidden flood (experimental):** compared with the average of the Jul 5 and Jul 17 baselines, HH rose by more than
   3 dB, the HH rise exceeds the HV rise by more than 2 dB, the pixel is not open or normal water, and it has valid data
   on all three dates. A 3×3 cleanup removes isolated pixels, and only pixels within about 500 m of same-date storm flood
   are kept. Not calculated for the baseline dates.
8. **At-risk cropland:** cropland flooded on 2+ consecutive passes
9. Compute area statistics per municipality
10. **Validate** with the Jun 23 false-alarm check and a −15 dB sensitivity run

## Run it locally

Tested with Python 3.11.

```bash
git clone https://github.com/jjjlyk/Signal-to-Noise.git
cd Signal-to-Noise
pip install -r requirements.txt
streamlit run app.py
```

The app opens at http://localhost:8501. Raw NISAR scenes are not included in this repo. The processed outputs in `data/`
and `tifs/` are all the app needs. To reprocess from scratch, download the scenes from
[ASF Vertex](https://search.asf.alaska.edu/) (Track 140A, Frame 9) and run the Colab notebook.

## Project structure

```
app.py                Streamlit app (all pages)
requirements.txt      Python dependencies
data/                 Flood statistics, municipality rankings, sensitivity check, study-area settings (bounds.json)
tifs/                 Per date: SAR RGB composite and flood thematic mask
                      Season-wide: flood duration, at-risk cropland, cropland, usual water, peak overlays
assets/logo/          Team logo (white and black versions)
assets/candaba/       Photos for the "Why Candaba?" slideshow
assets/team/          Team member photos
```

To update the team details, project links or slideshow photos, edit `TEAM_MEMBERS`, `PROJECT_LINKS` and
`CANDABA_PHOTOS` near the top of `app.py`.

## Team

**Signal to Noise**

| Member | Role | GitHub | LinkedIn |
|---|---|---|---|
| Jelyka Mae Dizon | Web App Developer | [@jjjlyk](https://github.com/jjjlyk) | [LinkedIn](https://www.linkedin.com/in/jelyka-mae-dizon-1b2753327) |
| Chrysler James Gaa | Flood Analysis and Impact Lead | [@rysll](https://github.com/rysll) | [LinkedIn](https://www.linkedin.com/in/chrysler-james-gaa-359576328/) |
| Rishon Simone Papa | SAR Data Acquisition and Preprocessing Lead | [@RSVPapa](https://github.com/RSVPapa) | [LinkedIn](https://www.linkedin.com/in/rishon-simone-papa-519516333/) |

## Sources

**Storms and flooding**
- [SunStar — Flooded villages reach 291 as of August 10](https://www.sunstar.com.ph/pampanga/flooded-villages-reach-291-as-of-august-10)
- [DZRH — TD Luis makes landfall over Maconacon, Isabela](https://www.dzrh.com.ph/post/td-luis-makes-landfall-over-maconacon-isabela)
- [Manila Bulletin — Maymay becomes a tropical storm](https://mb.com.ph/2026/08/05/pagasa-raises-signal-no-2-over-6-luzon-areas-as-maymay-becomes-tropical-storm)
- [Manila Bulletin — LPA develops into TD Neneng](https://mb.com.ph/2026/08/18/lpa-develops-into-tropical-depression-neneng)
- [Manila Bulletin — Neneng weakens, exits PAR](https://mb.com.ph/2026/08/20/neneng-weakens-into-an-lpa-exits-philippine-area-of-responsibility)
- [The Manila Times — Habagat puts Pampanga under state of calamity](https://www.manilatimes.net/2026/08/14/regions/habagat-puts-pampanga-under-state-of-calamity/2404999)
- [GMA News — 88 areas under state of calamity](https://www.gmanetwork.com/news/topstories/nation/999337/88-areas-under-state-of-calamity-due-to-habagat-luis-maymay/story/)
- [SunStar — 80 villages in Pampanga still flooded](https://www.sunstar.com.ph/pampanga/80-villages-in-pampanga-still-flooded-pdrrmo)

**Candaba and its farms**
- Nagumo, Ohara & Jaranilla-Sanchez (2026), *Journal of Disaster Research* 21(2) — the swamp's role in storing floodwaters
- Key Biodiversity Areas factsheet, Candaba Swamp — seasonal flooding, dry-season rice and watermelon, fishponds
- [SESAM field report, UP Los Baños](https://sesam.uplb.edu.ph/?p=785) — duck raising
- [GMA News — DA eyes Candaba Swamp waterway project to curb flooding](https://www.gmanetwork.com/news/topstories/regions/1001490/da-eyes-candaba-swamp-waterway-project-to-curb-flooding/story/)
- [Wikipedia — Candaba Swamp](https://en.wikipedia.org/wiki/Candaba_Swamp)
- [SunStar — The amazing farmer-fishermen of Candaba](https://www.sunstar.com.ph/article/1943787/pampanga/opinion/tantingco-the-amazing-farmer-fishermen-of-candaba) (opinion)

**Impact on farmers**
- [SunStar — Pampanga agri damage climbs to ₱917.6M](https://www.sunstar.com.ph/pampanga/pampanga-agri-damage-climbs-to-p9176-m)
- [Context.ph — PCIC allocates ₱187M for post-typhoon farmer insurance payouts](https://context.ph/2026/09/06/pcic-allocates-p187-million-for-post-typhoon-farmer-insurance-payouts/)

**Photos of Candaba**
- [Photo 1 — Expedia](https://www.expedia.com/Candaba.dx553248634304933708)
- [Photo 2 — Lakad Pilipinas](https://www.lakadpilipinas.com/2011/04/candaba-glorious-sunrise.html)
- [Photo 3 — GMA News](https://www.gmanetwork.com/news/topstories/regions/1001490/da-eyes-candaba-swamp-waterway-project-to-curb-flooding/story/)

**NISAR and SAR resources**
- [NISAR Data User Guide](https://nisar-docs.asf.alaska.edu/) · [ASF Data Search Vertex](https://search.asf.alaska.edu/) ·
  [NISAR Applications](https://nisar.jpl.nasa.gov/applications/societal-benefit/) ·
  [CSA SAR Python Tutorial](https://github.com/asc-csa/Synthetic_Aperture_Radar_Tutorial)

## License

Code released under the [MIT License](LICENSE). Photos belong to their original owners (see [Sources](#sources)).

*NASA does not endorse this project. NISAR data courtesy of NASA/JPL-Caltech and ISRO, distributed by the
Alaska Satellite Facility.*
