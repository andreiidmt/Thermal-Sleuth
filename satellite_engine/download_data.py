"""
Thermal Sleuth - Satellite Data Download
Downloads Sentinel-3 SLSTR WST products from Copernicus Data Space.
"""
import io
import os
import requests
import zipfile
from satellite_engine.config import DATA_DIR, ODATA_URL
from satellite_engine.auth import get_access_token


def ensure_data_dir(target_dir=None):
    """Create the data directory if it doesn't exist."""
    os.makedirs(target_dir or DATA_DIR, exist_ok=True)


def _score_netcdf_candidate(member_name):
    """Rank NetCDF files so WST-like files are preferred over auxiliary layers."""
    name = member_name.lower()
    score = 0

    if name.endswith(".nc"):
        score += 1
    if name.endswith("wst.nc"):
        score += 8
    if "wst" in name:
        score += 6
    if "sst" in name or "sea_surface_temperature" in name:
        score += 4
    if "geo" in name or "flag" in name:
        score -= 3

    return score


def extract_primary_netcdf(zip_path, output_dir=None):
    """
    Extract and return the most likely WST NetCDF file path from a product ZIP.

    Args:
        zip_path: Path to downloaded product .zip file.
        output_dir: Optional base output directory for extracted files.

    Returns:
        Absolute path to extracted NetCDF file, or None if none found.
    """
    if not zip_path or not os.path.exists(zip_path):
        print(f"[!] ZIP file not found: {zip_path}")
        return None

    if not zipfile.is_zipfile(zip_path):
        print(f"[!] Not a valid ZIP archive: {zip_path}")
        return None

    output_dir = output_dir or str(DATA_DIR)
    ensure_data_dir(output_dir)

    archive_name = os.path.splitext(os.path.basename(zip_path))[0]
    extract_root = os.path.join(output_dir, "extracted", archive_name)
    os.makedirs(extract_root, exist_ok=True)

    try:
        with zipfile.ZipFile(zip_path, "r") as zf:
            nc_members = [m for m in zf.namelist() if m.lower().endswith(".nc")]
            if not nc_members:
                print(f"[!] No NetCDF files found in: {os.path.basename(zip_path)}")
                return None

            primary_member = max(nc_members, key=_score_netcdf_candidate)
            extracted_path = os.path.join(extract_root, primary_member)

            if not os.path.exists(extracted_path):
                zf.extract(primary_member, path=extract_root)

            print(f"[+] NetCDF ready: {os.path.basename(extracted_path)}")
            return extracted_path
    except (zipfile.BadZipFile, OSError) as exc:
        print(f"[!] Failed to extract NetCDF from ZIP: {exc}")
        return None


def extract_primary_netcdf_bytes(zip_bytes, archive_name="product.zip"):
    """
    Extract and return the most likely WST NetCDF payload from ZIP bytes.

    Args:
        zip_bytes: ZIP archive content in memory.
        archive_name: Optional source name used in logs.

    Returns:
        Tuple (nc_bytes, nc_filename), or (None, None) if not found.
    """
    if not zip_bytes:
        print("[!] Empty ZIP payload provided.")
        return None, None

    try:
        with zipfile.ZipFile(io.BytesIO(zip_bytes), "r") as zf:
            nc_members = [m for m in zf.namelist() if m.lower().endswith(".nc")]
            if not nc_members:
                print(f"[!] No NetCDF files found in: {archive_name}")
                return None, None

            primary_member = max(nc_members, key=_score_netcdf_candidate)
            with zf.open(primary_member, "r") as nc_file:
                nc_bytes = nc_file.read()

            nc_filename = os.path.basename(primary_member) or "product.nc"
            print(f"[+] NetCDF loaded in memory: {nc_filename}")
            return nc_bytes, nc_filename
    except (zipfile.BadZipFile, OSError) as exc:
        print(f"[!] Failed to extract in-memory NetCDF: {exc}")
        return None, None


def download_product(product, output_dir=None):
    """
    Download a satellite product from Copernicus.

    Args:
        product: Product metadata dict from the OData API.
        output_dir: Directory to save to. Defaults to DATA_DIR.

    Returns:
        Path to the downloaded file, or None on failure.
    """
    token = get_access_token()
    if not token:
        print("[!] Cannot download without valid token.")
        return None

    output_dir = output_dir or str(DATA_DIR)
    ensure_data_dir(output_dir)

    product_id = product["Id"]
    product_name = product.get("Name", product_id)

    # Check if already downloaded
    output_path = os.path.join(output_dir, f"{product_name}.zip")
    if os.path.exists(output_path):
        print(f"[*] Already downloaded: {product_name}")
        return output_path

    # Download URL
    download_url = f"{ODATA_URL}({product_id})/$value"
    headers = {"Authorization": f"Bearer {token}"}

    print(f"[*] Downloading {product_name}...")

    try:
        response = requests.get(download_url, headers=headers, stream=True, timeout=120)
        if response.status_code == 200:
            with open(output_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            size_mb = os.path.getsize(output_path) / (1024 * 1024)
            print(f"[+] Downloaded: {product_name} ({size_mb:.1f} MB)")
            return output_path
        else:
            print(f"[!] Download failed: HTTP {response.status_code}")
            return None
    except requests.RequestException as e:
        print(f"[!] Download error: {e}")
        return None


def download_product_bytes(product):
    """
    Download a satellite product directly into memory.

    Args:
        product: Product metadata dict from the OData API.

    Returns:
        Raw ZIP bytes, or None on failure.
    """
    token = get_access_token()
    if not token:
        print("[!] Cannot download without valid token.")
        return None

    product_id = product["Id"]
    product_name = product.get("Name", product_id)
    download_url = f"{ODATA_URL}({product_id})/$value"
    headers = {"Authorization": f"Bearer {token}"}

    print(f"[*] Streaming {product_name} into memory...")

    try:
        response = requests.get(download_url, headers=headers, stream=True, timeout=120)
        if response.status_code != 200:
            print(f"[!] Download failed: HTTP {response.status_code}")
            return None

        payload = io.BytesIO()
        for chunk in response.iter_content(chunk_size=8192):
            if chunk:
                payload.write(chunk)

        zip_bytes = payload.getvalue()
        size_mb = len(zip_bytes) / (1024 * 1024)
        print(f"[+] Downloaded in memory: {product_name} ({size_mb:.1f} MB)")
        return zip_bytes
    except requests.RequestException as e:
        print(f"[!] Download error: {e}")
        return None


def download_batch(products, output_dir=None, max_downloads=5):
    """
    Download multiple products, up to a maximum.

    Returns:
        List of successfully downloaded file paths.
    """
    paths = []
    for product in products[:max_downloads]:
        path = download_product(product, output_dir)
        if path:
            paths.append(path)
    print(f"[+] Downloaded {len(paths)} / {min(len(products), max_downloads)} products.")
    return paths


if __name__ == "__main__":
    from satellite_engine.fetch_data import fetch_latest_pass
    print("=== Thermal Sleuth - Product Download ===")
    latest = fetch_latest_pass()
    if latest:
        download_product(latest)
