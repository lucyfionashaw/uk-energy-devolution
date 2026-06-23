# The Politics of Power

A data dashboard on the **politics of energy devolution in the UK** — who gets to build energy in Britain, and how the four nations' planning systems shape what gets approved.

🔗 **Live site:** _(GitHub Pages — see repo settings)_

## The story

Built around ~14,300 planning records (375 GW of proposed capacity) from the **Renewable Energy Planning Database (REPD, Q1 2026)**, joined to the **political control of every deciding local authority** (1973–2026).

| Page | Thread |
|------|--------|
| **Overview** (`index.html`) | The planning funnel: application → grant → built → operational. |
| **Four Nations** (`devolution.html`) | The local-vs-national decision route, and the collapse of English onshore wind after the 2015 de-facto ban. |
| **Party Politics** (`politics.html`) | Approval rates by controlling party — party only bites on contested onshore wind. |
| **The Machine** (`speed.html`) | Decision speed, capacity-weighting, and the 49.9 MW threshold-gaming around the NSIP cliff. |
| **What We Build** (`technology.html`) | The solar boom, the battery surge, and the onshore-wind divergence. |

## Tech

Static site — no build step for the pages themselves. Plain HTML + CSS, a single **Tahoma** font family (no web fonts), [Chart.js](https://www.chartjs.org/) from CDN, and the compiled analysis inlined into `data.js` (so it works on `file://` and GitHub Pages alike).

```
index.html devolution.html politics.html speed.html technology.html
styles.css          design system (Tahoma throughout; party/nation theming)
nav.js              shared top navigation
charts.js           colours, formatters, Chart.js defaults
data.js             GENERATED — all phases inlined as window.PHASE* globals
analysis/
  build_data_js.py  regenerates data.js from data/processed/*.json
  build_phase*.py    Cowork scripts that render the analysis workbook from the JSON
  REPD_devolution_analysis.xlsx
data/raw/           REPD CSV + the two council-history CSVs (public open data)
data/processed/     the eight phase JSONs — source of truth for data.js
```

To regenerate `data.js` after the analysis JSON changes: `py analysis/build_data_js.py`.

Phase → global map (note the names): `PHASE2` = council-party + Westminster-alignment, `PHASE2C` = decision-time weighting / 50 MW bunching, `PHASE2_REFRESH` = refreshed party + capacity ladder, `PHASE2B` = MP/constituency level, `PHASE3_LAND` / `PHASE3B_LAND` = capacity approved per km² of land controlled.

## Data sources

- Renewable Energy Planning Database (REPD), Q1 2026 — DESNZ
- UK local election results & council control, 1973–2026
- Planning Inspectorate / NSIP decisions

## Caveats

- Approval rates are calculated on **decided** applications only.
- Northern Ireland councils are not matched to the GB party-control dataset, so NI sits outside the party analysis (but is included in the four-nations comparisons).
- The Westminster-alignment cut is **descriptive, not causal** — it overlaps heavily with the 2015–2023 Conservative onshore-wind moratorium.
