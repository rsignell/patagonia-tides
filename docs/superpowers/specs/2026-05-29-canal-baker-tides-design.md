# Canal Baker Tidal Characterization — Design Spec

*2026-05-29*

---

## Problem

Tidal prediction for Canal Baker (Patagonian fjords, ~48°S) relies on the SHOA secondary port system (Pub. 3009) with Bahía Orange (~55°S, ~800km south) as the designated *puerto patrón*. Published height corrections for Canal Baker ports (Puerto Francisco, Puerto Brown) are absent, reflecting sparse observational basis. The tidal signal at Canal Baker enters exclusively through Golfo de Penas to the west; Peninsula Taitao blocks any northern tidal connection.

NASA/CNES SWOT (operational July 2023) provides the first opportunity for direct synoptic WSE observations across this network: ~3–5 passes per 21-day repeat cycle, ~30+ independent overpasses available. This project extracts those observations, compares them against existing tidal predictions, and characterizes the spatial pattern of tidal phase and amplitude across the network.

---

## Study area

```
SW: 48.74°S, 75.38°W
NE: 47.12°S, 73.23°W
```

22 sample points distributed across Canal Messier, Canal Baker, Canal Martínez, and Fiordo Steffen. Points placed mid-channel in QGIS to avoid banks, river mouths, and freshwater influence zones. P17 (Lago Merino Jarpa) is a landlocked calibration point providing per-pass instrument noise floor.

---

## Execution environment

| Item | Decision |
|---|---|
| Compute | Coiled notebook on AWS us-west-2 |
| SWOT data access | `earthaccess` direct S3 (no download) |
| FES2022 model files | Downloaded to `/scratch/fes2022/` on Coiled VM disk |
| Coiled disk size | 50 GB |
| Software environment | conda `environment.yml` passed to Coiled |
| Output | `s3://esip-qhub/canal-baker-tides/swot_wse_samples.parquet` |

Launch command:
```bash
coiled notebook start --name tides --software tides --disk-size 50
```

---

## Project structure

```
tides/
├── environment.yml          # conda env for Coiled
├── sample_points.csv        # 22 sample points (id, description, lat, lon)
├── 01_acquire.ipynb         # SWOT granule search, sampling, parquet output
└── 02_analyze.ipynb         # tidal predictions, residuals, plots
```

---

## environment.yml

```yaml
name: tides
channels:
  - conda-forge
dependencies:
  - python=3.11
  - earthaccess
  - xarray
  - h5py
  - h5netcdf
  - pyTMD
  - pandas
  - geopandas
  - matplotlib
  - cartopy
  - s3fs
  - fsspec
  - coiled
  - jupyterlab
```

---

## 01_acquire.ipynb

**Purpose:** Search SWOT L2_HR_Raster granules, sample WSE at 22 points via direct S3 access, write parquet.

**Cell sequence:**

1. **Imports + auth** — `earthaccess.login()` (netrc), `s3fs.S3FileSystem()`, load `sample_points.csv`
2. **Granule search** — `earthaccess.search_data(short_name="SWOT_L2_HR_Raster_2.0", bounding_box=..., temporal=("2023-07-01", None))`; bbox pre-filters to Canal Baker study area. *Note: verify exact short_name and version against earthaccess at implementation time.*
3. **Sampling loop** — for each granule:
   - open from S3 via `earthaccess.open()` → `xarray.open_dataset()`
   - for each of 22 points: nearest-pixel index, extract `wse`, `wse_qual`, `water_frac`, `cross_track`
   - retain rows where `wse_qual ∈ {0, 1}` and `water_frac > 0.9`
   - accumulate into list of dicts
4. **Write output** — `pd.DataFrame(rows)` → parquet to `s3://esip-qhub/canal-baker-tides/swot_wse_samples.parquet`
5. **Sanity check** — observation count per point; flag points with zero observations

**Key variables extracted per observation:**

| Variable | Description |
|---|---|
| `point_id` | Sample point ID (P01–P22) |
| `timestamp` | Overpass UTC time |
| `wse` | Water surface elevation (m, EGM2008) |
| `wse_qual` | Quality flag (0=good, 1=suspect) |
| `water_frac` | Water fraction at pixel |
| `cross_track` | Distance from nadir (m) |

---

## 02_analyze.ipynb

**Purpose:** Load parquet, compute tidal predictions, residual analysis, diagnostic plots.

**Cell sequence:**

1. **Imports + load data** — read parquet from S3, load `sample_points.csv`
2. **FES2022 setup** — check `/scratch/fes2022/`; download via pyTMD AVISO utility if missing (AVISO credentials via netrc); initialize pyTMD tide model object
3. **Tidal predictions** — for each observation row:
   - **FES2022**: pyTMD constituent prediction at point coordinates and timestamp
   - **SHOA+offset**: Bahía Orange patron time series (loaded from `bahia_orange_predictions.csv`) + published secondary port offsets for P07 (Puerto Francisco) and P12 (Puerto Brown); raw Bahía Orange value used for all other points. *This CSV must be manually exported from the SHOA online predictor covering July 2023 → present before running this notebook.*
4. **Residuals** — `residual_fes = wse - tide_fes2022`, `residual_shoa = wse - tide_shoa`
5. **P17 noise floor** — per-pass RMS of P17 (Lago Merino Jarpa) WSE; provides instrument noise floor for interpreting channel residuals
6. **Diagnostics:**
   - Per-point residual time series (both models)
   - Spatial map of mean residual magnitude across the network
   - Along-canal phase/amplitude profile (P01 → P22, west-to-east)

---

## Data sources

| Dataset | Source | Role |
|---|---|---|
| SWOT L2_HR_Raster 100m | NASA PO.DAAC via earthaccess S3 | Primary WSE observations |
| FES2022 | AVISO (downloaded to Coiled VM) | Independent tidal prediction |
| SHOA Pub. 3009 secondary port corrections | SHOA | Phase offsets for P07, P12 |
| Bahía Orange patron predictions | SHOA online predictor (CSV export) | SHOA baseline time series |

---

## Limitations

- ~30 independent overpasses: dominant constituents (M2, S2) may be resolvable; minor constituent separation is not expected
- Nadir gap (~20km) means some channel locations may be missing from individual passes
- Freshwater influence from Río Baker near Caleta Tortel (P14, P20) — eastern point results should be interpreted cautiously
- FES2022 performance in enclosed fjord systems is not well validated
- No in-situ validation data; results are internally consistent only

---

## Out of scope (Phase 2)

Longitudinal WSE profile extraction along Canal Baker and Canal Messier axes, including Angostura Inglesa hydraulic head validation. Depends on Phase 1 establishing baseline WSE quality and noise characteristics.
