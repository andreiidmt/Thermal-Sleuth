"""
Thermal Sleuth - EU-Wide Satellite Data Fetching
Queries Copernicus STAC/OData API for Sentinel-3 SLSTR Water Surface Temperature
products across the full EU bounding box. Supports incremental polling.
"""
import json
import os
import requests
from datetime import datetime, timezone, timedelta
from satellite_engine.config import (
    ODATA_URL, EU_BBOX, COLLECTION_NAME, PRODUCT_TYPE, FETCH_STATE_MODE
)
from satellite_engine.auth import get_access_token

try:
    from shapely.geometry import box, shape
    HAS_SHAPELY = True
except ImportError:
    HAS_SHAPELY = False


# Track last processed product to avoid re-processing
_state_file = os.path.join(os.path.dirname(__file__), ".fetch_state.json")
_state_memory = {"last_processed_time": None, "processed_ids": []}
_eu_bbox_polygon = box(*EU_BBOX) if HAS_SHAPELY else None
_warned_shapely_missing = False


def _product_intersects_eu(product):
    """Return True when a product footprint intersects the configured EU bounding box."""
    global _warned_shapely_missing

    if not HAS_SHAPELY:
        if not _warned_shapely_missing:
            print("[*] shapely not installed; skipping EU footprint filtering.")
            _warned_shapely_missing = True
        return True

    footprint = product.get("GeoFootprint")
    if not footprint:
        return True

    try:
        return shape(footprint).intersects(_eu_bbox_polygon)
    except Exception:
        # Keep product when footprint parsing fails to avoid false drops.
        return True


def _load_state():
    """Load the last-processed state from disk."""
    if FETCH_STATE_MODE == "memory":
        return {
            "last_processed_time": _state_memory.get("last_processed_time"),
            "processed_ids": list(_state_memory.get("processed_ids", [])),
        }

    if os.path.exists(_state_file):
        with open(_state_file, "r", encoding="utf-8") as f:
            return json.load(f)

    return {"last_processed_time": None, "processed_ids": []}


def _save_state(state):
    """Persist the fetch state."""
    # Keep only last 500 IDs to prevent unbounded growth
    state["processed_ids"] = state.get("processed_ids", [])[-500:]

    if FETCH_STATE_MODE == "memory":
        _state_memory["last_processed_time"] = state.get("last_processed_time")
        _state_memory["processed_ids"] = list(state.get("processed_ids", []))
        return

    with open(_state_file, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)


def fetch_eu_wide(days_back=30, max_results=50, incremental=True):
    """
    Fetch Sentinel-3 SLSTR WST products covering the EU.

    Args:
        days_back: How many days back to search.
        max_results: Maximum number of products to return.
        incremental: If True, skip already-processed products.

    Returns:
        List of product metadata dicts.
    """
    token = get_access_token()
    if not token:
        print("[!] Cannot fetch data without valid token.")
        return []

    state = _load_state() if incremental else {"last_processed_time": None, "processed_ids": []}

    # Time range
    end_time = datetime.now(timezone.utc)
    start_time = end_time - timedelta(days=days_back)

    # Build OData filter
    # Filter for Sentinel-3 WST products
    time_filter = (
        f"ContentDate/Start ge {start_time.strftime('%Y-%m-%dT%H:%M:%S.000Z')} "
        f"and ContentDate/Start le {end_time.strftime('%Y-%m-%dT%H:%M:%S.000Z')}"
    )
    collection_filter = f"Collection/Name eq '{COLLECTION_NAME}' and contains(Name, '{PRODUCT_TYPE}')"
    full_filter = f"{collection_filter} and {time_filter}"

    params = {
        "$filter": full_filter,
        "$orderby": "ContentDate/Start desc",
        "$top": str(max_results),
    }
    headers = {"Authorization": f"Bearer {token}"}

    print(f"[*] Fetching EU-wide Sentinel-3 SLSTR WST data ({days_back} days back)...")

    try:
        response = requests.get(ODATA_URL, params=params, headers=headers, timeout=30)
        if response.status_code != 200:
            print(f"[!] OData query failed: {response.status_code}")
            return []

        data = response.json()
        products = data.get("value", [])
        print(f"[+] Found {len(products)} satellite products.")

        filtered_products = [p for p in products if _product_intersects_eu(p)]
        if len(filtered_products) != len(products):
            print(
                f"[+] EU footprint filter kept {len(filtered_products)} / {len(products)} products."
            )
        products = filtered_products

        # Filter out already processed
        if incremental and state["processed_ids"]:
            new_products = [p for p in products if p["Id"] not in state["processed_ids"]]
            print(f"[+] {len(new_products)} are new (not yet processed).")
            products = new_products

        # Update state
        for p in products:
            state["processed_ids"].append(p["Id"])
        if products:
            state["last_processed_time"] = datetime.now(timezone.utc).isoformat()
        _save_state(state)

        return products

    except requests.RequestException as e:
        print(f"[!] Network error fetching data: {e}")
        return []


def fetch_latest_pass():
    """
    Fetch only the single most recent satellite pass.
    Useful for real-time alerts.
    """
    token = get_access_token()
    if not token:
        return None

    params = {
        "$filter": f"Collection/Name eq '{COLLECTION_NAME}' and contains(Name, '{PRODUCT_TYPE}')",
        "$orderby": "ContentDate/Start desc",
        "$top": "1",
    }
    headers = {"Authorization": f"Bearer {token}"}

    try:
        response = requests.get(ODATA_URL, params=params, headers=headers, timeout=15)
        if response.status_code == 200:
            data = response.json()
            if data.get("value"):
                product = data["value"][0]
                print(f"[+] Latest pass: {product['Name']}")
                return product
    except requests.RequestException as e:
        print(f"[!] Error fetching latest pass: {e}")

    return None


def get_product_download_url(product_id, token):
    """Get the download URL for a specific product."""
    return f"{ODATA_URL}({product_id})/$value"


if __name__ == "__main__":
    print("=== Thermal Sleuth - EU-Wide Data Fetch ===")
    products = fetch_eu_wide(days_back=7, max_results=10)
    for i, p in enumerate(products[:5]):
        print(f"  [{i+1}] {p['Name']}")
        print(f"      Time: {p['ContentDate']['Start']}")
        print(f"      ID: {p['Id']}")