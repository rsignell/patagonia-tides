"""
Copy FES2022 model files from local disk to S3 cache.
Run this once after the AVISO download completes.

Usage (in Coiled notebook):
    %run fes2022_to_s3.py
"""
import subprocess
from pathlib import Path

LOCAL_DIR = Path("/scratch/fes2022")
S3_URI = "s3://esip-qhub/fes2022/"

files = list(LOCAL_DIR.glob("**/*.nc"))
if not files:
    print(f"No .nc files found in {LOCAL_DIR}. Nothing to upload.")
else:
    print(f"Syncing {len(files)} files from {LOCAL_DIR} → {S3_URI}")
    r = subprocess.run(
        ["aws", "s3", "sync", str(LOCAL_DIR), S3_URI, "--no-progress"],
        text=True,
    )
    if r.returncode == 0:
        print("Done.")
    else:
        print(f"aws s3 sync exited with code {r.returncode}")
