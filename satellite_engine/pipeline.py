"""
Thermal Sleuth - Pipeline Orchestrator
Runs the full satellite-to-evidence pipeline:
  fetch -> download -> analyze -> tag -> export
"""
import json
import os
import argparse
import tempfile
from datetime import datetime, timezone

from satellite_engine.config import SAMPLE_DATA_DIR
from satellite_engine.fetch_data import fetch_eu_wide, fetch_latest_pass
from satellite_engine.download_data import (
    download_product,
    extract_primary_netcdf,
    download_product_bytes,
    extract_primary_netcdf_bytes,
)
from satellite_engine.analyze_thermal import analyze_wst_netcdf, analyze_product_metadata
from satellite_engine.galileo_tag import create_evidence_package
from satellite_engine.facilities_db import find_nearest_facility


COUNTRY_NAMES = {
    "RO": "Romania", "FR": "France", "DE": "Germany", "IT": "Italy",
    "ES": "Spain", "PL": "Poland", "NL": "Netherlands", "GR": "Greece",
    "BG": "Bulgaria", "CZ": "Czech Republic",
}


def _normalize_iso_datetime(value):
    """Normalize datetime strings so API consumers can parse consistently."""
    if not value:
        return datetime.now(timezone.utc).isoformat()
    return value.replace("Z", "+00:00") if isinstance(value, str) else str(value)


def _build_geojson_feature(evidence, anomaly):
    """Convert an analyzed anomaly + evidence package into dashboard GeoJSON format."""
    nearest = anomaly.get("nearest_facility")
    detection_time = _normalize_iso_datetime(
        evidence.get("detection_timestamp_utc") or anomaly.get("satellite_pass_time")
    )
    pass_time = _normalize_iso_datetime(
        anomaly.get("satellite_pass_time") or evidence.get("satellite_source", {}).get("acquisition_time_utc")
    )

    country_code = anomaly.get("country", "Unknown")
    country_name = COUNTRY_NAMES.get(country_code, country_code)

    return {
        "type": "Feature",
        "geometry": {
            "type": "Point",
            "coordinates": [round(anomaly["lon"], 4), round(anomaly["lat"], 4)],
        },
        "properties": {
            "anomaly_id": evidence["anomaly_id"],
            "temperature_delta": round(anomaly.get("temperature_delta", 0.0), 1),
            "absolute_temp": round(anomaly.get("absolute_temp", 0.0), 1),
            "baseline_temp": round(anomaly.get("baseline_temp", 0.0), 1),
            "affected_area_km2": round(anomaly.get("affected_area_km2", 0.0), 2),
            "confidence_score": round(anomaly.get("confidence_score", 0.0), 3),
            "severity": evidence.get("severity", "LOW"),
            "country": country_code,
            "country_name": country_name,
            "water_body": anomaly.get("water_body", "Unknown"),
            "detection_time": detection_time,
            "satellite_pass_time": pass_time,
            "pass_type": anomaly.get("pass_type", "nighttime"),
            "nearest_facility": nearest["name"] if nearest else None,
            "facility_distance_km": nearest.get("distance_km") if nearest else None,
            "facility_type": nearest.get("type") if nearest else None,
        },
    }


def _build_stats(features, satellite_passes_processed, scan_started_at):
    """Build summary stats payload compatible with dashboard widgets."""
    now = datetime.now(timezone.utc)
    props_list = [f["properties"] for f in features]

    if not props_list:
        return {
            "total_anomalies": 0,
            "countries_with_alerts": 0,
            "country_list": [],
            "average_temperature_delta": 0.0,
            "max_temperature_delta": 0.0,
            "critical_count": 0,
            "high_count": 0,
            "moderate_count": 0,
            "monitoring_area_km2": 10_500_000,
            "by_country": {},
            "last_scan_utc": now.isoformat(),
            "satellite_passes_processed": satellite_passes_processed,
            "system_uptime_hours": round((now - scan_started_at).total_seconds() / 3600.0, 2),
        }

    countries_with_alerts = sorted(set(p["country"] for p in props_list if p.get("country") and p["country"] != "Unknown"))
    avg_delta = sum(p["temperature_delta"] for p in props_list) / len(props_list)
    max_delta = max(p["temperature_delta"] for p in props_list)
    critical_count = sum(1 for p in props_list if p["severity"] == "CRITICAL")
    high_count = sum(1 for p in props_list if p["severity"] == "HIGH")
    moderate_count = sum(1 for p in props_list if p["severity"] == "MODERATE")

    by_country = {}
    for p in props_list:
        c_name = p.get("country_name") or p.get("country", "Unknown")
        by_country[c_name] = by_country.get(c_name, 0) + 1

    return {
        "total_anomalies": len(props_list),
        "countries_with_alerts": len(countries_with_alerts),
        "country_list": countries_with_alerts,
        "average_temperature_delta": round(avg_delta, 1),
        "max_temperature_delta": round(max_delta, 1),
        "critical_count": critical_count,
        "high_count": high_count,
        "moderate_count": moderate_count,
        "monitoring_area_km2": 10_500_000,
        "by_country": dict(sorted(by_country.items(), key=lambda item: -item[1])),
        "last_scan_utc": now.isoformat(),
        "satellite_passes_processed": satellite_passes_processed,
        "system_uptime_hours": round((now - scan_started_at).total_seconds() / 3600.0, 2),
    }


def _export_live_outputs(features, evidence_lookup, stats):
    """Write live dashboard payload files alongside sample data files."""
    os.makedirs(SAMPLE_DATA_DIR, exist_ok=True)

    anomalies_path = os.path.join(str(SAMPLE_DATA_DIR), "live_anomalies.geojson")
    evidence_path = os.path.join(str(SAMPLE_DATA_DIR), "live_evidence.json")
    stats_path = os.path.join(str(SAMPLE_DATA_DIR), "live_stats.json")

    geojson = {"type": "FeatureCollection", "features": features}

    with open(anomalies_path, "w", encoding="utf-8") as f:
        json.dump(geojson, f, indent=2)

    with open(evidence_path, "w", encoding="utf-8") as f:
        json.dump(evidence_lookup, f, indent=2)

    with open(stats_path, "w", encoding="utf-8") as f:
        json.dump(stats, f, indent=2)

    print(f" Live anomalies saved: {anomalies_path}")
    print(f" Live evidence saved:  {evidence_path}")
    print(f" Live stats saved:     {stats_path}")


def run_pipeline(days_back=7, max_products=5, download=False, persist_downloads=False):
    """
    Run the full Thermal Sleuth pipeline.

    Args:
        days_back: How many days to search back.
        max_products: Maximum products to process.
        download: If True, download and analyze actual NetCDF data.
                  If False, just fetch metadata and create evidence records.
        persist_downloads: If True, store downloaded ZIP/NetCDF under ./data.
                           If False, process downloads in memory with temporary files.
    """
    print("=" * 60)
    print(" THERMAL SLEUTH - EU-Wide Thermal Pollution Pipeline")
    print("=" * 60)
    print(f" Search window: {days_back} days")
    print(f" Max products:  {max_products}")
    print(f" Download mode: {'Full analysis' if download else 'Metadata only'}")
    if download:
        storage_mode = "Persistent local cache" if persist_downloads else "In-memory (no local cache)"
        print(f" Storage mode:  {storage_mode}")
    print("=" * 60)

    scan_started_at = datetime.now(timezone.utc)

    # Step 1: Fetch satellite products
    print("\n[STEP 1] Fetching EU-wide Sentinel-3 SLSTR WST products...")
    products = fetch_eu_wide(days_back=days_back, max_results=max_products)

    if not products:
        print("[!] No products found. Check credentials and network.")
        return {
            "products": 0,
            "anomalies": 0,
            "evidence": 0,
        }

    print(f"\n[+] Retrieved {len(products)} products from Copernicus.")

    # Step 2: Process products
    all_features = []
    evidence_lookup = {}
    processed_products = 0

    if download:
        # Full pipeline: download and analyze
        print("\n[STEP 2] Downloading satellite data...")
        print("\n[STEP 3] Analyzing thermal data for anomalies...")

        for i, product in enumerate(products[:max_products]):
            print(f"\n  -> Product {i + 1}/{min(len(products), max_products)}")
            product_name = product.get("Name", product.get("Id", ""))
            if persist_downloads:
                zip_path = download_product(product)
                if not zip_path:
                    continue

                nc_path = extract_primary_netcdf(zip_path)
                if not nc_path:
                    continue

                anomalies = analyze_wst_netcdf(nc_path)
            else:
                zip_bytes = download_product_bytes(product)
                if not zip_bytes:
                    continue

                nc_bytes, nc_name = extract_primary_netcdf_bytes(
                    zip_bytes,
                    archive_name=f"{product_name}.zip",
                )
                if not nc_bytes:
                    continue

                with tempfile.TemporaryDirectory(prefix="thermal_sleuth_") as temp_dir:
                    temp_nc_path = os.path.join(temp_dir, nc_name)
                    with open(temp_nc_path, "wb") as f:
                        f.write(nc_bytes)
                    anomalies = analyze_wst_netcdf(temp_nc_path)

            processed_products += 1
            product_time = _normalize_iso_datetime(product.get("ContentDate", {}).get("Start", ""))

            for anomaly in anomalies:
                nearest = anomaly.get("nearest_facility") or find_nearest_facility(anomaly["lat"], anomaly["lon"])
                anomaly["nearest_facility"] = nearest
                anomaly["satellite_pass_time"] = product_time
                anomaly["satellite_id"] = product_name
                anomaly["country"] = nearest["country"] if nearest else "Unknown"
                anomaly["water_body"] = nearest["water_body"] if nearest else "Unknown"

                evidence = create_evidence_package(anomaly)
                evidence["detection_timestamp_utc"] = product_time

                feature = _build_geojson_feature(evidence, anomaly)
                all_features.append(feature)
                evidence_lookup[evidence["anomaly_id"]] = evidence

        all_features.sort(key=lambda feature: feature["properties"]["detection_time"], reverse=True)

        stats = _build_stats(all_features, processed_products, scan_started_at)
        _export_live_outputs(all_features, evidence_lookup, stats)
    else:
        # Metadata-only mode: log products for tracking
        print("\n[STEP 2] Processing product metadata...")
        for i, product in enumerate(products):
            info = analyze_product_metadata(product)
            print(f"  [{i+1}] {info['product_name'][:60]}...")
            print(f"       Acquired: {info['acquisition_time']}")
        processed_products = len(products)

    anomaly_count = len(all_features)
    evidence_count = len(evidence_lookup)

    # Step 3: Summary
    print("\n" + "=" * 60)
    print(" PIPELINE COMPLETE")
    print("=" * 60)
    print(f" Products retrieved:   {len(products)}")
    print(f" Products processed:   {processed_products}")
    print(f" Anomalies detected:   {anomaly_count}")
    print(f" Evidence packages:    {evidence_count}")

    return {
        "products": processed_products,
        "anomalies": anomaly_count,
        "evidence": evidence_count,
    }


def run_latest():
    """Quick check: fetch only the latest satellite pass and report."""
    print("\n[*] Fetching latest Sentinel-3 SLSTR pass...")
    product = fetch_latest_pass()
    if product:
        print(f"[+] Latest product: {product['Name']}")
        print(f"    Time: {product['ContentDate']['Start']}")
        print(f"    ID: {product['Id']}")
        return product
    else:
        print("[!] Could not fetch latest pass.")
        return None


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Thermal Sleuth Pipeline")
    parser.add_argument("--days", type=int, default=7, help="Days to search back")
    parser.add_argument("--max", type=int, default=10, help="Max products to process")
    parser.add_argument("--download", action="store_true", help="Download and analyze NetCDF data")
    parser.add_argument(
        "--persist-downloads",
        action="store_true",
        help="Persist satellite ZIP/NetCDF files under ./data (default is in-memory processing)",
    )
    parser.add_argument("--latest", action="store_true", help="Just fetch the latest pass")

    args = parser.parse_args()

    if args.latest:
        run_latest()
    else:
        run_pipeline(
            days_back=args.days,
            max_products=args.max,
            download=args.download,
            persist_downloads=args.persist_downloads,
        )
