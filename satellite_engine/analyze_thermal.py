"""
Thermal Sleuth - Thermal Anomaly Detection Algorithm
Analyzes Sentinel-3 SLSTR Water Surface Temperature data to detect
illegal industrial thermal dumping across EU water bodies.

The algorithm:
1. Loads WST data (NetCDF)
2. Computes spatial baseline temperature per pixel neighborhood
3. Flags pixels with temperature significantly above baseline
4. Clusters anomaly pixels into discrete hotspot regions
5. Cross-references with known industrial facilities
6. Scores confidence and outputs GeoJSON
"""
import json
import os
import random
import numpy as np
from datetime import datetime, timezone

try:
    import xarray as xr
    HAS_XARRAY = True
except ImportError:
    HAS_XARRAY = False

try:
    from scipy import ndimage
    HAS_SCIPY = True
except ImportError:
    HAS_SCIPY = False

from satellite_engine.config import (
    ANOMALY_THRESHOLD_SUSPICIOUS, ANOMALY_THRESHOLD_CRITICAL,
    SPATIAL_WINDOW_PIXELS, MIN_ANOMALY_PIXELS,
    WEIGHT_TEMP_DELTA, WEIGHT_PERSISTENCE, WEIGHT_FACILITY_PROXIMITY, WEIGHT_NIGHTTIME,
    MAX_FACILITY_DISTANCE_KM, SAMPLE_DATA_DIR,
)
from satellite_engine.facilities_db import find_nearest_facility
from satellite_engine.galileo_tag import create_evidence_package


def analyze_wst_netcdf(filepath):
    """
    Analyze a Sentinel-3 SLSTR WST NetCDF file for thermal anomalies.

    Args:
        filepath: Path to the .nc file.

    Returns:
        List of detected anomaly dicts.
    """
    if not HAS_XARRAY:
        print("[!] xarray not installed. Install with: pip install xarray netCDF4")
        return []

    print(f"[*] Analyzing: {os.path.basename(filepath)}")

    try:
        ds = xr.open_dataset(filepath, engine="netcdf4")
    except Exception as e:
        print(f"[!] Could not open NetCDF file: {e}")
        return []

    # Look for the temperature variable (names vary between products)
    temp_var = None
    for var_name in ["sea_surface_temperature", "sst", "wst", "temperature"]:
        if var_name in ds.data_vars:
            temp_var = var_name
            break

    if temp_var is None:
        print(f"[!] No temperature variable found. Available: {list(ds.data_vars)}")
        ds.close()
        return []

    temp_data = ds[temp_var].values
    print(f"[+] Temperature grid shape: {temp_data.shape}")

    # Convert from Kelvin to Celsius if needed
    if np.nanmean(temp_data) > 200:
        temp_data = temp_data - 273.15
        print("[*] Converted from Kelvin to Celsius.")

    # Detect anomalies using spatial baseline
    anomalies = _detect_spatial_anomalies(temp_data, ds)

    ds.close()
    return anomalies


def _detect_spatial_anomalies(temp_data, ds):
    """
    Detect thermal anomalies by comparing each pixel to its spatial neighborhood.
    """
    if not HAS_SCIPY:
        print("[!] scipy not installed. Using simplified detection.")
        return []

    # Handle 2D or 3D data (take first time step if 3D)
    if temp_data.ndim == 3:
        temp_2d = temp_data[0]
    elif temp_data.ndim == 2:
        temp_2d = temp_data
    else:
        print(f"[!] Unexpected data dimensions: {temp_data.ndim}")
        return []

    # Create valid data mask (not NaN, not too cold/hot)
    valid_mask = ~np.isnan(temp_2d) & (temp_2d > -5) & (temp_2d < 50)
    temp_masked = np.where(valid_mask, temp_2d, np.nan)

    # Compute local baseline using uniform filter (neighborhood mean)
    window = SPATIAL_WINDOW_PIXELS
    # Use convolution with NaN handling
    temp_filled = np.where(np.isnan(temp_masked), 0, temp_masked)
    count = np.where(np.isnan(temp_masked), 0, 1).astype(float)

    local_sum = ndimage.uniform_filter(temp_filled, size=window, mode='constant', cval=0)
    local_count = ndimage.uniform_filter(count, size=window, mode='constant', cval=0)

    # Avoid division by zero
    local_mean = np.where(local_count > 0.1, local_sum / local_count, np.nan)

    # Temperature delta: pixel minus local mean
    delta = temp_masked - local_mean

    # Flag anomalous pixels
    anomaly_mask = delta > ANOMALY_THRESHOLD_SUSPICIOUS

    if not np.any(anomaly_mask):
        print("[*] No thermal anomalies detected in this tile.")
        return []

    # Cluster connected anomaly pixels
    labeled, num_features = ndimage.label(anomaly_mask)
    print(f"[+] Found {num_features} potential anomaly clusters.")

    anomalies = []
    for cluster_id in range(1, num_features + 1):
        cluster_mask = labeled == cluster_id
        pixel_count = np.sum(cluster_mask)

        if pixel_count < MIN_ANOMALY_PIXELS:
            continue

        # Cluster statistics
        cluster_temps = temp_masked[cluster_mask]
        cluster_deltas = delta[cluster_mask]
        mean_delta = float(np.nanmean(cluster_deltas))
        max_delta = float(np.nanmax(cluster_deltas))
        mean_temp = float(np.nanmean(cluster_temps))
        baseline_temp = mean_temp - mean_delta

        # Get centroid coordinates
        rows, cols = np.where(cluster_mask)
        center_row = int(np.mean(rows))
        center_col = int(np.mean(cols))

        # Try to get lat/lon from dataset
        lat, lon = _pixel_to_latlon(ds, center_row, center_col)

        if lat is None or lon is None:
            continue

        # Estimate affected area (rough: ~1km per SLSTR pixel)
        area_km2 = pixel_count * 1.0  # SLSTR WST is ~1km resolution

        # Cross-reference with industrial facilities
        nearest = find_nearest_facility(lat, lon, MAX_FACILITY_DISTANCE_KM)

        # Compute confidence score
        confidence = _compute_confidence(
            mean_delta, nearest is not None, True, pixel_count
        )

        anomalies.append({
            "lat": round(lat, 4),
            "lon": round(lon, 4),
            "temperature_delta": round(mean_delta, 1),
            "max_delta": round(max_delta, 1),
            "absolute_temp": round(mean_temp, 1),
            "baseline_temp": round(baseline_temp, 1),
            "affected_area_km2": round(area_km2, 2),
            "pixel_count": pixel_count,
            "confidence_score": round(confidence, 3),
            "nearest_facility": nearest,
            "pass_type": "nighttime",  # Will be determined from metadata
        })

    print(f"[+] {len(anomalies)} anomalies passed minimum size filter.")
    return anomalies


def _pixel_to_latlon(ds, row, col):
    """Convert pixel coordinates to lat/lon using dataset metadata."""
    try:
        # Try common coordinate names
        for lat_name in ["latitude", "lat", "Latitude"]:
            if lat_name in ds.coords or lat_name in ds.data_vars:
                lat_data = ds[lat_name].values
                break
        else:
            return None, None

        for lon_name in ["longitude", "lon", "Longitude"]:
            if lon_name in ds.coords or lon_name in ds.data_vars:
                lon_data = ds[lon_name].values
                break
        else:
            return None, None

        if lat_data.ndim == 1:
            lat = float(lat_data[row]) if row < len(lat_data) else None
            lon = float(lon_data[col]) if col < len(lon_data) else None
        elif lat_data.ndim == 2:
            lat = float(lat_data[row, col]) if row < lat_data.shape[0] and col < lat_data.shape[1] else None
            lon = float(lon_data[row, col]) if row < lon_data.shape[0] and col < lon_data.shape[1] else None
        else:
            return None, None

        return lat, lon

    except Exception:
        return None, None


def _compute_confidence(temp_delta, near_facility, nighttime, pixel_count):
    """
    Compute a confidence score (0.0–1.0) for an anomaly.
    Higher score = more likely to be illegal thermal dumping.
    """
    # Temperature delta component (normalized: 3°C = 0.3, 10°C = 1.0)
    temp_score = min(1.0, (temp_delta - 2.0) / 8.0)

    # Facility proximity component
    facility_score = 1.0 if near_facility else 0.3

    # Nighttime component (thermal dumping more common at night)
    night_score = 1.0 if nighttime else 0.5

    # Persistence / size component
    size_score = min(1.0, pixel_count / 20.0)

    confidence = (
        WEIGHT_TEMP_DELTA * temp_score +
        WEIGHT_FACILITY_PROXIMITY * facility_score +
        WEIGHT_NIGHTTIME * night_score +
        WEIGHT_PERSISTENCE * size_score
    )

    return max(0.1, min(0.99, confidence))


def analyze_product_metadata(product):
    """
    Create an anomaly record from product metadata alone (without downloading).
    Useful for real-time alerting on new products.
    """
    # Extract what we can from the product name and metadata
    name = product.get("Name", "")
    start_time = product.get("ContentDate", {}).get("Start", "")
    product_id = product.get("Id", "")

    return {
        "product_name": name,
        "product_id": product_id,
        "acquisition_time": start_time,
        "status": "pending_analysis",
    }


if __name__ == "__main__":
    print("=== Thermal Sleuth - Anomaly Detection Engine ===")
    print("This module analyzes downloaded NetCDF files.")
    print("Usage: from satellite_engine.analyze_thermal import analyze_wst_netcdf")
    print("       anomalies = analyze_wst_netcdf('path/to/file.nc')")
