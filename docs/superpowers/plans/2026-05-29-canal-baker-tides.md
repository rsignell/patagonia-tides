# Canal Baker Tidal Characterization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build two Jupyter notebooks that extract SWOT WSE observations at 22 sample points across Canal Baker, compare them against FES2022 and SHOA tidal predictions, and characterize tidal phase/amplitude across the fjord network.

**Architecture:** `01_acquire.ipynb` searches SWOT L2_HR_Raster granules via earthaccess and streams data directly from NASA S3 without downloading, sampling 22 mid-channel points and writing a parquet file to S3. `02_analyze.ipynb` loads that parquet, runs FES2022 (via pyTMD) and SHOA+offset predictions, computes residuals, and produces diagnostic plots. Both notebooks run on a Coiled cloud VM (AWS us-west-2) defined by a conda `environment.yml`.

**Tech Stack:** Python 3.11, earthaccess, xarray, h5netcdf, pyTMD (FES2022), pandas, s3fs, coiled, jupyterlab, matplotlib

---

## File map

| File | Role |
|---|---|
| `environment.yml` | conda env spec — used by Coiled to build cloud software image |
| `sample_points.csv` | 22 sample point coordinates (shared by both notebooks) |
| `bahia_orange_predictions.csv` | Bahía Orange patron tide series — manually exported from SHOA predictor, not committed to git |
| `01_acquire.ipynb` | SWOT granule search → S3 sampling → parquet output |
| `02_analyze.ipynb` | Load parquet → FES2022 + SHOA predictions → residuals → plots |

---

## Task 1: Project scaffolding

**Files:**
- Create: `environment.yml`
- Create: `sample_points.csv`
- Create: `.gitignore`

- [ ] **Step 1: Initialize git repo**

```bash
cd /home/rsignell/repos/tides
git init
```

- [ ] **Step 2: Create `.gitignore`**

```
bahia_orange_predictions.csv
/scratch/
*.parquet
__pycache__/
.ipynb_checkpoints/
.env
```

- [ ] **Step 3: Create `environment.yml`**

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

- [ ] **Step 4: Create `sample_points.csv`**

```csv
id,description,lat,lon
P01,Golfo de Penas — western anchor,-47.6554,-74.7902
P02,Canal Messier north,-47.7228,-74.7571
P03,Canal Messier mid-north,-47.8429,-74.7297
P04,Canal Messier mid,-47.9349,-74.6720
P05,Canal Messier mid-south,-48.0305,-74.6446
P06,Canal Messier south,-48.1195,-74.6143
P07,Puerto Francisco (SHOA anchor),-47.7833,-74.6000
P08,Canal Baker west,-47.8348,-74.4915
P09,Canal Baker west-mid,-47.9261,-74.4319
P10,Canal Baker mid,-47.9808,-74.2755
P11,Canal Baker mid-east,-47.9599,-74.1035
P12,Puerto Brown vicinity (SHOA anchor),-47.9682,-73.9409
P13,Canal Baker east,-47.9960,-73.7736
P14,Canal Baker / Tortel approach,-48.0390,-73.5695
P15,Canal Martínez / Baker junction,-47.8088,-73.7377
P16,Fiordo Steffen,-47.6842,-73.7084
P17,Lago Merino Jarpa (calibration),-47.8706,-74.0876
P18,Canal Martínez,-47.7734,-74.2110
P19,Canal Baker north,-47.7959,-74.0130
P20,Eastern extent — toward Yungay,-48.1178,-73.4908
P21,Canal Martínez south,-47.7510,-74.3837
P22,Baker / Messier confluence,-47.9475,-74.5417
```

- [ ] **Step 5: Register Coiled software environment**

```bash
coiled software create --name tides --conda environment.yml
```

Expected: environment builds successfully (takes a few minutes on first run).

- [ ] **Step 6: Commit**

```bash
git add environment.yml sample_points.csv .gitignore
git commit -m "feat: project scaffolding — env, sample points, gitignore"
```

---

## Task 2: Verify SWOT granule search

**Purpose:** Confirm earthaccess auth, find the correct SWOT short_name, and inspect actual variable names before writing the full acquisition notebook. Do not commit this scratch work.

- [ ] **Step 1: Start Coiled notebook**

```bash
coiled notebook start --name tides --software tides --disk-size 50
```

Open the URL printed to the terminal. Create a new notebook named `scratch_search.ipynb` (not committed).

- [ ] **Step 2: Test auth and search**

```python
import earthaccess
earthaccess.login()

results = earthaccess.search_data(
    short_name="SWOT_L2_HR_Raster_2.0",
    bounding_box=(-75.38, -48.74, -73.23, -47.12),  # (W, S, E, N)
    temporal=("2023-07-01", None),
    count=10,
)
print(f"Granules found (sample): {len(results)}")
if results:
    print(results[0])
```

Expected: at least 1 result. If 0 results, check the correct short_name at https://podaac.jpl.nasa.gov and search for "SWOT L2 HR Raster". Update `SWOT_SHORT_NAME` in Task 3 accordingly.

- [ ] **Step 3: Inspect variable names**

```python
import xarray as xr
files = earthaccess.open([results[0]])
ds = xr.open_dataset(files[0], engine='h5netcdf')
print(list(ds.data_vars))
print(list(ds.coords))
print(ds)
```

Expected: dataset containing `wse`, `wse_qual`, `water_frac`, and 2D `latitude`/`longitude` variables. Note any name differences — update `sample_granule` in Task 4 to match actual names.

- [ ] **Step 4: Check time representation**

```python
time_vars = [v for v in list(ds.coords) + list(ds.data_vars) if 'time' in v.lower()]
print("Time variables:", time_vars)
for v in time_vars:
    print(v, "→", ds[v].values)
```

Note which variable holds the overpass timestamp. Update `sample_granule` in Task 4 to use the correct variable name.

- [ ] **Step 5: Run full granule count**

```python
all_results = earthaccess.search_data(
    short_name="SWOT_L2_HR_Raster_2.0",
    bounding_box=(-75.38, -48.74, -73.23, -47.12),
    temporal=("2023-07-01", None),
)
print(f"Total granules: {len(all_results)}")
```

Note this number — it informs how long the acquisition loop will take.

---

## Task 3: Build `01_acquire.ipynb` — setup and search

**Files:**
- Create: `01_acquire.ipynb`

- [ ] **Step 1: Create notebook — title cell**

Create `01_acquire.ipynb`. Add a markdown cell:

```markdown
# SWOT WSE Acquisition — Canal Baker

Searches SWOT L2_HR_Raster granules via earthaccess, samples WSE at 22
mid-channel points via direct S3 access (no download), and writes results
to S3 parquet.

**Output:** `s3://esip-qhub/canal-baker-tides/swot_wse_samples.parquet`

**Run on:** Coiled notebook (`coiled notebook start --name tides --software tides --disk-size 50`)
```

- [ ] **Step 2: Add imports and config cell**

```python
import earthaccess
import xarray as xr
import pandas as pd
import numpy as np
import s3fs

# Verify short_name against Task 2 findings
SWOT_SHORT_NAME = "SWOT_L2_HR_Raster_2.0"
BBOX = (-75.38, -48.74, -73.23, -47.12)   # (W, S, E, N)
TEMPORAL = ("2023-07-01", None)
OUTPUT_PATH = "s3://esip-qhub/canal-baker-tides/swot_wse_samples.parquet"

GOOD_QUAL = {0, 1}           # 0=good, 1=suspect; discard 2=degraded, 3=bad
WATER_FRAC_THRESHOLD = 0.9
```

- [ ] **Step 3: Add auth and sample points cell**

```python
earthaccess.login()

points = pd.read_csv("sample_points.csv")
print(f"Loaded {len(points)} sample points")
display(points)
```

Execute. Expected: table of 22 rows.

- [ ] **Step 4: Add granule search cell**

```python
results = earthaccess.search_data(
    short_name=SWOT_SHORT_NAME,
    bounding_box=BBOX,
    temporal=TEMPORAL,
)
print(f"Found {len(results)} granules")
```

Execute. Expected: nonzero count matching Task 2.

- [ ] **Step 5: Commit**

```bash
git add 01_acquire.ipynb
git commit -m "feat: 01_acquire.ipynb — imports, config, auth, search"
```

---

## Task 4: Build `01_acquire.ipynb` — sampling loop

**Files:**
- Modify: `01_acquire.ipynb`

- [ ] **Step 1: Add point-sampling helper cell**

```python
def sample_granule(ds, points):
    """
    Extract WSE at each sample point from one SWOT L2_HR_Raster granule.
    Uses nearest-pixel lookup on the 2D lat/lon grid.
    Returns list of dicts; skips points with no valid pixel.
    """
    lat_grid = ds["latitude"].values   # 2D array (y, x) — update name if Task 2 found different
    lon_grid = ds["longitude"].values  # 2D array (y, x)

    # Extract overpass timestamp from granule
    if "time" in ds:
        timestamp = pd.Timestamp(ds["time"].values.flat[0])
    elif "time_tai" in ds:
        timestamp = pd.Timestamp(ds["time_tai"].values.flat[0])
    else:
        timestamp = None  # update variable name from Task 2 findings

    rows = []
    for _, pt in points.iterrows():
        dist = (lat_grid - pt["lat"]) ** 2 + (lon_grid - pt["lon"]) ** 2
        if np.all(np.isnan(dist)):
            continue
        idx = np.unravel_index(np.nanargmin(dist), dist.shape)

        wse = float(ds["wse"].values[idx])
        wse_qual = int(ds["wse_qual"].values[idx])
        water_frac = float(ds["water_frac"].values[idx])
        cross_track = float(ds["cross_track"].values[idx]) if "cross_track" in ds else np.nan

        if wse_qual in GOOD_QUAL and water_frac > WATER_FRAC_THRESHOLD and not np.isnan(wse):
            rows.append({
                "point_id": pt["id"],
                "lat": pt["lat"],
                "lon": pt["lon"],
                "timestamp": timestamp,
                "wse": wse,
                "wse_qual": wse_qual,
                "water_frac": water_frac,
                "cross_track": cross_track,
            })
    return rows
```

- [ ] **Step 2: Test helper on one granule**

```python
test_files = earthaccess.open([results[0]])
test_ds = xr.open_dataset(test_files[0], engine='h5netcdf')
test_rows = sample_granule(test_ds, points)
print(f"Valid observations from test granule: {len(test_rows)}")
if test_rows:
    display(pd.DataFrame(test_rows))
```

Execute. Expected: 0 or more rows (most granules won't cover all 22 points). If a `KeyError` occurs, the variable name differs from what the helper expects — update `lat_grid`, `lon_grid`, or the quality/water_frac references using the names found in Task 2.

- [ ] **Step 3: Add full sampling loop**

```python
all_rows = []

for i, granule in enumerate(results):
    if i % 50 == 0:
        print(f"  {i+1}/{len(results)} granules — {len(all_rows)} observations so far")
    try:
        files = earthaccess.open([granule])
        ds = xr.open_dataset(files[0], engine='h5netcdf')
        rows = sample_granule(ds, points)
        all_rows.extend(rows)
        ds.close()
    except Exception as e:
        print(f"  Skipped granule {i}: {e}")

print(f"\nTotal valid observations: {len(all_rows)}")
```

Execute. Runs until all granules are processed; prints progress every 50 granules.

---

## Task 5: Build `01_acquire.ipynb` — output and sanity check

**Files:**
- Modify: `01_acquire.ipynb`

- [ ] **Step 1: Add output cell**

```python
df = pd.DataFrame(all_rows)
df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
df = df.sort_values(["point_id", "timestamp"]).reset_index(drop=True)

fs = s3fs.S3FileSystem()
with fs.open(OUTPUT_PATH, "wb") as f:
    df.to_parquet(f, index=False)

print(f"Wrote {len(df)} rows to {OUTPUT_PATH}")
print(f"Date range: {df['timestamp'].min()} → {df['timestamp'].max()}")
```

Execute. Expected: confirmation message with nonzero row count.

- [ ] **Step 2: Add sanity check cell**

```python
obs_per_point = (
    df.groupby("point_id").size()
    .reindex(points["id"])
    .fillna(0)
    .astype(int)
    .rename("n_obs")
)
display(obs_per_point.to_frame())

zero = obs_per_point[obs_per_point == 0]
if len(zero):
    print(f"WARNING: {len(zero)} points with zero observations: {list(zero.index)}")
    print("These points likely fall in the SWOT nadir gap for both pass geometries.")
else:
    print("All 22 points have at least one observation.")
```

Execute. Note any zero-observation points for interpretation in the analysis notebook.

- [ ] **Step 3: Commit completed acquisition notebook**

```bash
git add 01_acquire.ipynb
git commit -m "feat: complete 01_acquire.ipynb — sampling loop, S3 parquet output, sanity check"
```

---

## Task 6: Build `02_analyze.ipynb` — setup and FES2022

**Files:**
- Create: `02_analyze.ipynb`

**Prerequisite (manual, before running):** Export Bahía Orange tide predictions from the SHOA online predictor (http://www.shoa.cl/php/mareas.php) for the period 2023-07-01 → present. Save as `bahia_orange_predictions.csv` in the project root with columns `datetime` (ISO 8601 UTC) and `tide_m` (meters). This file is gitignored.

- [ ] **Step 1: Create notebook — title cell**

Create `02_analyze.ipynb`. Add markdown cell:

```markdown
# SWOT Tidal Residual Analysis — Canal Baker

Loads SWOT WSE parquet from S3, computes FES2022 and SHOA+offset tidal
predictions, and characterizes tidal signal across the Canal Baker network.

**Prerequisites:**
- `bahia_orange_predictions.csv` in project root (manually exported from SHOA predictor)
- FES2022 model files (downloaded automatically to `/scratch/fes2022/` on first run)

**Input:** `s3://esip-qhub/canal-baker-tides/swot_wse_samples.parquet`
```

- [ ] **Step 2: Add imports and config cell**

```python
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import s3fs
import pyTMD
from pathlib import Path

INPUT_PATH = "s3://esip-qhub/canal-baker-tides/swot_wse_samples.parquet"
FES2022_DIR = Path("/scratch/fes2022")
SHOA_CSV = Path("bahia_orange_predictions.csv")

# Time offsets (minutes) from Pub. 3009 — tide arrives this many minutes
# after Bahía Orange at each SHOA anchor port. Look these up in Pub. 3009
# for Puerto Francisco (P07) and Puerto Brown (P12) and update below.
SHOA_OFFSETS = {
    "P07": 0,   # TODO: replace with published Pub. 3009 value for Puerto Francisco
    "P12": 0,   # TODO: replace with published Pub. 3009 value for Puerto Brown
}
```

- [ ] **Step 3: Add data load cell**

```python
fs = s3fs.S3FileSystem()
with fs.open(INPUT_PATH, "rb") as f:
    df = pd.read_parquet(f)
df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)

points = pd.read_csv("sample_points.csv")

print(f"Loaded {len(df)} observations across {df['point_id'].nunique()} points")
print(f"Date range: {df['timestamp'].min()} → {df['timestamp'].max()}")
display(df.head())
```

Execute. Expected: observation count matching Task 5 output.

- [ ] **Step 4: Add FES2022 download cell**

```python
FES2022_DIR.mkdir(parents=True, exist_ok=True)

existing = list(FES2022_DIR.glob("**/*.nc"))
if not existing:
    print("Downloading FES2022 from AVISO — requires AVISO credentials in ~/.netrc")
    print("See: https://pytmd.readthedocs.io/en/latest/getting_started/FES.html")
    import subprocess
    r = subprocess.run(
        ["python", "-m", "pyTMD.download_FES_Tidal_Models",
         "--directory", str(FES2022_DIR),
         "--model", "FES2022",
         "--tide", "ocean"],
        capture_output=True, text=True
    )
    print(r.stdout[-2000:] if r.stdout else "")
    if r.returncode != 0:
        print("DOWNLOAD ERROR:", r.stderr[-1000:])
        raise RuntimeError("FES2022 download failed — see output above and pyTMD docs")
else:
    print(f"FES2022 already present: {len(existing)} files in {FES2022_DIR}")
```

Execute. If download fails, follow the pyTMD documentation link printed above.

- [ ] **Step 5: Commit notebook skeleton**

```bash
git add 02_analyze.ipynb
git commit -m "feat: 02_analyze.ipynb skeleton — imports, config, data load, FES2022 setup"
```

---

## Task 7: Build `02_analyze.ipynb` — tidal predictions and residuals

**Files:**
- Modify: `02_analyze.ipynb`

- [ ] **Step 1: Add FES2022 prediction helper cell**

```python
def predict_fes2022(lon, lat, timestamps, model_dir):
    """
    Predict tide height at (lon, lat) for a list of UTC timestamps using FES2022.
    Returns numpy array of tide heights in meters.
    """
    epoch = pd.Timestamp("2000-01-01", tz="UTC")
    delta_time = np.array(
        [(t - epoch).total_seconds() for t in timestamps], dtype=float
    )
    tide = pyTMD.compute.tide_elevations(
        np.atleast_1d(float(lon)),
        np.atleast_1d(float(lat)),
        delta_time,
        DIRECTORY=str(model_dir),
        MODEL="FES2022",
        EPOCH=(2000, 1, 1, 0, 0, 0),
        TYPE="time series",
        TIME="UTC",
        FILL_VALUE=np.nan,
    )
    return np.asarray(tide).flatten()

# Smoke test on first point
pt0 = points.iloc[0]
pt0_rows = df[df["point_id"] == pt0["id"]]
pt0_pred = predict_fes2022(pt0["lon"], pt0["lat"], pt0_rows["timestamp"].tolist(), FES2022_DIR)
print(f"FES2022 predictions for {pt0['id']} ({len(pt0_pred)} values): {pt0_pred[:5]}")
```

Execute. Expected: array of tide heights in meters. If pyTMD raises an API error, check the installed pyTMD version (`import pyTMD; print(pyTMD.__version__)`) and consult the pyTMD changelog for any renamed arguments.

- [ ] **Step 2: Add SHOA prediction helper cell**

```python
assert SHOA_CSV.exists(), (
    f"{SHOA_CSV} not found. Export Bahía Orange tide predictions from "
    "http://www.shoa.cl/php/mareas.php (2023-07-01 → present) and save "
    "with columns: datetime (UTC ISO 8601), tide_m (meters)."
)

shoa_raw = pd.read_csv(SHOA_CSV, parse_dates=["datetime"])
shoa_raw["datetime"] = pd.to_datetime(shoa_raw["datetime"], utc=True)
shoa_ts = shoa_raw.set_index("datetime").sort_index()

def predict_shoa(point_id, timestamps):
    """
    Interpolate Bahía Orange patron tide at given timestamps, applying
    the published secondary port time offset for P07 and P12.
    All other points use the raw Bahía Orange value (offset = 0).
    Returns numpy array of tide heights in meters.
    """
    offset_min = SHOA_OFFSETS.get(point_id, 0)
    adjusted = [t - pd.Timedelta(minutes=offset_min) for t in timestamps]
    shoa_epoch = shoa_ts.index.map(lambda x: x.timestamp()).values
    shoa_vals = shoa_ts["tide_m"].values
    return np.array([
        np.interp(t.timestamp(), shoa_epoch, shoa_vals,
                  left=np.nan, right=np.nan)
        for t in adjusted
    ])

# Smoke test
pt0_shoa = predict_shoa(pt0["id"], pt0_rows["timestamp"].tolist())
print(f"SHOA predictions for {pt0['id']}: {pt0_shoa[:5]}")
```

Execute. Expected: array of tide heights.

- [ ] **Step 3: Add full prediction and residual computation cell**

```python
records = []
for pt_id, group in df.groupby("point_id"):
    pt_info = points[points["id"] == pt_id].iloc[0]
    timestamps = group["timestamp"].tolist()

    fes_pred = predict_fes2022(pt_info["lon"], pt_info["lat"], timestamps, FES2022_DIR)
    shoa_pred = predict_shoa(pt_id, timestamps)

    for i, (_, row) in enumerate(group.iterrows()):
        records.append({
            "point_id": pt_id,
            "timestamp": row["timestamp"],
            "wse": row["wse"],
            "wse_qual": row["wse_qual"],
            "tide_fes2022": fes_pred[i],
            "tide_shoa": shoa_pred[i],
            "residual_fes": row["wse"] - fes_pred[i],
            "residual_shoa": row["wse"] - shoa_pred[i],
        })

results = pd.DataFrame(records)
print(results.groupby("point_id")[["residual_fes", "residual_shoa"]].describe().round(3))
```

Execute. Expected: per-point residual statistics table.

- [ ] **Step 4: Commit**

```bash
git add 02_analyze.ipynb
git commit -m "feat: FES2022 and SHOA tidal predictions, residual computation"
```

---

## Task 8: Build `02_analyze.ipynb` — noise floor and diagnostic plots

**Files:**
- Modify: `02_analyze.ipynb`

- [ ] **Step 1: Add P17 noise floor cell**

```python
p17 = results[results["point_id"] == "P17"].copy()
noise_floor_rms = float(np.sqrt(np.nanmean(p17["wse"] ** 2))) if len(p17) else np.nan
print(f"P17 (Lago Merino Jarpa) — {len(p17)} overpasses")
print(f"  WSE range : {p17['wse'].min():.3f} → {p17['wse'].max():.3f} m")
print(f"  Noise RMS : {noise_floor_rms:.3f} m")
print("P17 has no tidal connection; this RMS is instrument + atmospheric noise.")
```

Execute. Expected: noise floor in the 0.01–0.10 m range. Values larger than ~0.20 m suggest a data quality issue worth investigating before interpreting channel residuals.

- [ ] **Step 2: Add per-point residual time series plot**

```python
point_order = points["id"].tolist()
fig, axes = plt.subplots(len(point_order), 1,
                         figsize=(14, 3 * len(point_order)), sharex=True)

for ax, pt_id in zip(axes, point_order):
    pt_data = results[results["point_id"] == pt_id]
    ax.scatter(pt_data["timestamp"], pt_data["residual_fes"],
               s=25, label="FES2022", color="steelblue", zorder=3)
    ax.scatter(pt_data["timestamp"], pt_data["residual_shoa"],
               s=25, label="SHOA", color="tomato", alpha=0.7, zorder=3)
    ax.axhline(0, color="k", lw=0.5)
    ax.axhspan(-noise_floor_rms, noise_floor_rms,
               alpha=0.12, color="gray", label="P17 noise floor")
    ax.set_ylabel(f"{pt_id}\n(m)", fontsize=8)
    if pt_id == point_order[0]:
        ax.legend(fontsize=7, loc="upper right")

axes[0].set_title("SWOT WSE Residuals vs Tidal Predictions — Canal Baker")
axes[-1].xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
fig.tight_layout()
plt.savefig("residual_timeseries.png", dpi=150, bbox_inches="tight")
plt.show()
```

Execute. Expected: stacked time series, one row per point.

- [ ] **Step 3: Add spatial RMS-residual map**

```python
rms_fes = (
    results.groupby("point_id")["residual_fes"]
    .apply(lambda x: np.sqrt(np.nanmean(x**2)))
    .reindex(points["id"])
)

fig, ax = plt.subplots(figsize=(10, 8))
sc = ax.scatter(
    points["lon"], points["lat"],
    c=rms_fes.values, s=90, cmap="RdYlGn_r", vmin=0, vmax=1.0, zorder=3
)
for _, pt in points.iterrows():
    ax.annotate(pt["id"], (pt["lon"], pt["lat"]),
                fontsize=7, xytext=(4, 4), textcoords="offset points")
plt.colorbar(sc, ax=ax, label="RMS residual vs FES2022 (m)")
ax.set_xlabel("Longitude")
ax.set_ylabel("Latitude")
ax.set_title("Spatial Pattern of SWOT–FES2022 Residuals — Canal Baker Network")
ax.set_aspect("equal")
fig.tight_layout()
plt.savefig("residual_spatial.png", dpi=150, bbox_inches="tight")
plt.show()
```

Execute. Expected: scatter map showing spatial pattern of model skill across the network.

- [ ] **Step 4: Add along-canal WSE profile**

```python
# West-to-east transect from Golfo de Penas to Caleta Tortel
canal_profile = ["P01", "P22", "P08", "P09", "P10", "P11", "P12", "P13", "P14"]

mean_wse = results[results["point_id"].isin(canal_profile)].groupby("point_id")["wse"].mean()
std_wse  = results[results["point_id"].isin(canal_profile)].groupby("point_id")["wse"].std()

fig, ax = plt.subplots(figsize=(10, 4))
x = range(len(canal_profile))
ax.errorbar(
    x,
    [mean_wse.get(p, np.nan) for p in canal_profile],
    yerr=[std_wse.get(p, np.nan) for p in canal_profile],
    marker="o", capsize=4, color="steelblue", label="Mean ± std SWOT WSE"
)
ax.set_xticks(list(x))
ax.set_xticklabels(canal_profile)
ax.set_xlabel("Sample point (west → east, Golfo de Penas → Caleta Tortel)")
ax.set_ylabel("WSE (m, EGM2008)")
ax.set_title("Along-Canal WSE Profile — Canal Baker")
ax.legend()
fig.tight_layout()
plt.savefig("canal_profile.png", dpi=150, bbox_inches="tight")
plt.show()
```

Execute. Expected: west-to-east WSE profile with error bars showing variability across overpasses.

- [ ] **Step 5: Final commit**

```bash
git add 02_analyze.ipynb residual_timeseries.png residual_spatial.png canal_profile.png
git commit -m "feat: complete 02_analyze.ipynb — noise floor, residual plots, canal profile"
```

---

*End of plan.*
