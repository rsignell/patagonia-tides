"""
Restore FES2022 model files from S3 cache to local disk.
Run this at the start of a new Coiled session instead of re-downloading from AVISO.

Usage (in Coiled notebook):
    %run fes2022_from_s3.py
"""
import subprocess
from pathlib import Path

S3_URI = "s3://esip-qhub/fes2022/"
LOCAL_DIR = Path("/scratch/fes2022")

LOCAL_DIR.mkdir(parents=True, exist_ok=True)

# Check that the S3 cache exists
check = subprocess.run(
    ["aws", "s3", "ls", S3_URI],
    capture_output=True, text=True,
)
if not check.stdout.strip():
    print(f"No files found at {S3_URI}.")
    print("Run fes2022_to_s3.py after a successful AVISO download first.")
else:
    print(f"Syncing FES2022 from {S3_URI} → {LOCAL_DIR}")
    r = subprocess.run(
        ["aws", "s3", "sync", S3_URI, str(LOCAL_DIR), "--no-progress"],
        text=True,
    )
    if r.returncode == 0:
        files = list(LOCAL_DIR.glob("**/*.nc"))
        print(f"Done — {len(files)} files in {LOCAL_DIR}")
    else:
        print(f"aws s3 sync exited with code {r.returncode}")
