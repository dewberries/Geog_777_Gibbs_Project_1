from pathlib import Path
from datetime import datetime
import os
import math

import arcpy
from arcpy import sa

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

import numpy as np
from matplotlib.patches import Polygon
from matplotlib.collections import PatchCollection

from .config import (
    WELLS_SHP, TRACTS_SHP,
    NITRATE_FIELD, CANCER_FIELD, TRACT_ID_FIELD,
    CELL_SIZE, NEIGHBORS,
    OVERWRITE_OUTPUTS
)

# GIS processing pipeline for the Cancer–Nitrate Analysis App
def run_pipeline(k: float, out_base: str, log=None, progress_callback=None) -> dict:

    # Helper functions for logging, progress, and error handling.
    def say(msg: str):
        if log:
            log(msg)

    # Progress callback.
    def prog(pct: int):
        if progress_callback:
            progress_callback(pct)        

    # Error handling helper
    def stop(msg: str):
        raise RuntimeError(msg)

    arcpy.env.overwriteOutput = OVERWRITE_OUTPUTS

    if k <= 1:
        stop("k must be > 1")

    repo_root = Path(__file__).resolve().parents[1]
    wells_path = str(repo_root / WELLS_SHP)
    tracts_path = str(repo_root / TRACTS_SHP)

    if not arcpy.Exists(wells_path):
        stop(f"Wells shapefile not found: {wells_path}")
    if not arcpy.Exists(tracts_path):
        stop(f"Tracts shapefile not found: {tracts_path}")

    wells_fields = [f.name for f in arcpy.ListFields(wells_path)]
    tracts_fields = [f.name for f in arcpy.ListFields(tracts_path)]

    if NITRATE_FIELD not in wells_fields:
        stop(f"Field '{NITRATE_FIELD}' not found in wells shapefile.")
    if CANCER_FIELD not in tracts_fields:
        stop(f"Field '{CANCER_FIELD}' not found in tracts shapefile.")
    if TRACT_ID_FIELD not in tracts_fields:
        stop(f"Field '{TRACT_ID_FIELD}' not found in tracts shapefile.")

    def is_numeric(fc, field_name):
        f = arcpy.ListFields(fc, field_name)[0]
        return f.type in ("Integer", "SmallInteger", "Single", "Double")

    if not is_numeric(wells_path, NITRATE_FIELD):
        stop(f"Wells field '{NITRATE_FIELD}' must be numeric.")
    if not is_numeric(tracts_path, CANCER_FIELD):
        stop(f"Tracts field '{CANCER_FIELD}' must be numeric.")

    def must_be_projected(fc_path):
        sr = arcpy.Describe(fc_path).spatialReference
        if sr is None:
            stop(f"Missing spatial reference: {fc_path}")
        if hasattr(sr, "type") and sr.type == "Geographic":
            stop(f"Inputs must be projected (meters/feet), not degrees.\nLayer: {fc_path}\nSR: {sr.name}")

    must_be_projected(wells_path)
    must_be_projected(tracts_path)

    # Spatial Analyst required
    if arcpy.CheckExtension("Spatial") != "Available":
        stop("Spatial Analyst extension not available (required).")
    arcpy.CheckOutExtension("Spatial")

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_k = str(k).replace(".", "p")
    run_dir = Path(out_base) / f"run_k{safe_k}_{ts}"
    run_dir.mkdir(parents=True, exist_ok=True)

    prog(5) 

    gdb = run_dir / "outputs.gdb"
    if not arcpy.Exists(str(gdb)):
        arcpy.management.CreateFileGDB(str(run_dir), "outputs.gdb")
    say(f"Output GDB: {gdb}")

    prog(15)

    say("Copying inputs into output GDB...")
    wells_fc = os.path.join(str(gdb), "wells")
    tracts_fc = os.path.join(str(gdb), "cancer_tracts")
    arcpy.management.CopyFeatures(wells_path, wells_fc)
    arcpy.management.CopyFeatures(tracts_path, tracts_fc)

    prog(30) 

    say("Running IDW...")
    neighborhood = sa.RadiusVariable(NEIGHBORS)
    idw_raster = os.path.join(str(gdb), f"nitrate_idw_k{safe_k}")
    idw = sa.Idw(wells_fc, NITRATE_FIELD, CELL_SIZE, k, neighborhood)
    idw.save(idw_raster)
    say(f"IDW complete...")

    prog(55)

    say("Running Zonal Statistics As Table (MEAN)...")
    zonal_table = os.path.join(str(gdb), f"zonal_mean_k{safe_k}")
    sa.ZonalStatisticsAsTable(
        in_zone_data=tracts_fc,
        zone_field=TRACT_ID_FIELD,
        in_value_raster=idw_raster,
        out_table=zonal_table,
        ignore_nodata="DATA",
        statistics_type="MEAN"
    )
    say(f"Zonal stats complete...")

    prog(70)

    say("Joining mean nitrate back to tracts...")
    joined_fc = os.path.join(str(gdb), f"tracts_joined_k{safe_k}")
    arcpy.management.CopyFeatures(tracts_fc, joined_fc)

    arcpy.management.JoinField(
        in_data=joined_fc,
        in_field=TRACT_ID_FIELD,
        join_table=zonal_table,
        join_field=TRACT_ID_FIELD,
        fields=["MEAN"]
    )

    prog(80)

    # Rename MEAN -> mean_nitrate (simple approach)
    if not arcpy.ListFields(joined_fc, "mean_nitrate"):
        arcpy.management.AddField(joined_fc, "mean_nitrate", "DOUBLE")
    arcpy.management.CalculateField(joined_fc, "mean_nitrate", "!MEAN!", "PYTHON3")
    arcpy.management.DeleteField(joined_fc, ["MEAN"])
    say(f"Joined tracts...")

    say("Running regression (OLS)...")
    x_vals = []
    y_vals = []
    with arcpy.da.SearchCursor(joined_fc, ["mean_nitrate", CANCER_FIELD]) as cur:
        for mean_n, canrate in cur:
            if mean_n is None or canrate is None:
                continue
            x_vals.append(float(mean_n))
            y_vals.append(float(canrate))

    x = np.array(x_vals)
    y = np.array(y_vals)

    X = np.column_stack([np.ones_like(x), x])
    beta, _, _, _ = np.linalg.lstsq(X, y, rcond=None)
    b0 = float(beta[0])
    b1 = float(beta[1])

    y_hat = X @ beta
    ss_res = float(np.sum((y - y_hat) ** 2))
    ss_tot = float(np.sum((y - np.mean(y)) ** 2))
    r2 = 1.0 - (ss_res / ss_tot if ss_tot != 0 else math.nan)

    reg_path = run_dir / f"summary_regression_k{safe_k}.txt"
    with open(reg_path, "w", encoding="utf-8") as f:
        f.write("Summary\n")
        f.write("=====================\n\n")
        f.write(f"k: {k}\n")
        f.write(f"cell size: {CELL_SIZE}\n")
        f.write(f"neighbors: {NEIGHBORS}\n\n")
        f.write("OLS Regression Report\n")
        f.write("=====================\n\n")
        f.write(f"Model: {CANCER_FIELD} = b0 + b1 * mean_nitrate\n\n")
        f.write(f"n: {len(x)}\n")
        f.write(f"b0: {b0:.6f}\n")
        f.write(f"b1: {b1:.6f}\n")
        f.write(f"R^2: {r2:.6f}\n\n")
    say(f"Summary and Regression report: {reg_path}")

    prog(90) 

    say("Exporting map PNG (static)...")
    extent = arcpy.Describe(joined_fc).extent
    xmin, ymin, xmax, ymax = extent.XMin, extent.YMin, extent.XMax, extent.YMax

    patches = []
    values = []

    with arcpy.da.SearchCursor(joined_fc, ["SHAPE@", "mean_nitrate"]) as cur:
        for geom, val in cur:
            if geom is None or val is None:
                continue
            for part in geom:
                coords = [(p.X, p.Y) for p in part if p is not None]
                if len(coords) < 3:
                    continue
                patches.append(Polygon(coords, closed=True))
                values.append(float(val))

    fig, ax = plt.subplots(figsize=(8.5, 6.0), dpi=150)
    pc = PatchCollection(patches, array=np.array(values), linewidths=0.2)
    ax.add_collection(pc)
    ax.set_xlim(xmin, xmax)
    ax.set_ylim(ymin, ymax)
    ax.set_aspect("equal", adjustable="box")
    ax.set_xticks([])
    ax.set_yticks([])
    ax.set_title(f"Mean Nitrate by Tract (k={k}, cell={CELL_SIZE}, neighbors={NEIGHBORS})")
    cbar = fig.colorbar(pc, ax=ax, shrink=0.85)
    cbar.set_label("Mean nitrate")
    fig.tight_layout()

    png_path = run_dir / f"map_k{safe_k}.png"
    fig.savefig(png_path)
    plt.close(fig)
    say(f"Map PNG: {png_path}")

    prog(100)

    return {
        "run_dir": str(run_dir),
        "gdb": str(gdb),
        "joined_fc": joined_fc,
        "regression_report": str(reg_path),
        "map_png": str(png_path),
    }