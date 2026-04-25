"""
Thermal Sleuth — Central Configuration
EU-wide real-time thermal pollution monitoring.
"""
import os
from dotenv import load_dotenv

load_dotenv()

# ─── Copernicus API ───────────────────────────────────────────────
COPERNICUS_CLIENT_ID = os.getenv("COPERNICUS_CLIENT_ID", "")
COPERNICUS_CLIENT_SECRET = os.getenv("COPERNICUS_CLIENT_SECRET", "")
TOKEN_URL = "https://identity.dataspace.copernicus.eu/auth/realms/CDSE/protocol/openid-connect/token"
ODATA_URL = "https://catalogue.dataspace.copernicus.eu/odata/v1/Products"
STAC_URL = "https://stac.dataspace.copernicus.eu/v1/"

# ─── EU-Wide Bounding Box ────────────────────────────────────────
# Full European Union coverage: Atlantic → Black Sea, Mediterranean → Arctic
EU_BBOX = [-25.0, 34.0, 45.0, 72.0]

# ─── Sentinel-3 SLSTR Collection ─────────────────────────────────
COLLECTION_NAME = "SENTINEL-3"
PRODUCT_TYPE = "SL_2_WST"  # Water Surface Temperature

# ─── Anomaly Detection Thresholds ────────────────────────────────
ANOMALY_THRESHOLD_SUSPICIOUS = 3.0   # °C above local mean → suspicious
ANOMALY_THRESHOLD_CRITICAL = 5.0     # °C above local mean → high confidence
SPATIAL_WINDOW_PIXELS = 15           # Neighborhood window for baseline calc
MIN_ANOMALY_PIXELS = 4               # Minimum cluster size to count as real

# ─── Confidence Scoring Weights ──────────────────────────────────
WEIGHT_TEMP_DELTA = 0.35
WEIGHT_PERSISTENCE = 0.25
WEIGHT_FACILITY_PROXIMITY = 0.25
WEIGHT_NIGHTTIME = 0.15

# ─── Monitoring ──────────────────────────────────────────────────
POLL_INTERVAL_SECONDS = 1800  # 30 minutes
MAX_FACILITY_DISTANCE_KM = 10.0  # Max distance to link anomaly → facility

# ─── Runtime Behavior ───────────────────────────────────────────
# Keep incremental-fetch state in memory by default to avoid local file writes.
# Set THERMAL_FETCH_STATE_MODE=disk if you want persisted state across restarts.
FETCH_STATE_MODE = os.getenv("THERMAL_FETCH_STATE_MODE", "memory").strip().lower()
if FETCH_STATE_MODE not in {"memory", "disk"}:
	FETCH_STATE_MODE = "memory"

# ─── Paths ───────────────────────────────────────────────────────
import pathlib
PROJECT_ROOT = pathlib.Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "data"
SAMPLE_DATA_DIR = PROJECT_ROOT / "backend" / "sample_data"
DB_PATH = PROJECT_ROOT / "backend" / "thermal_sleuth.db"
