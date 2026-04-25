"""
Thermal Sleuth — Copernicus OAuth2 Authentication
Handles token acquisition and caching for the Data Space Ecosystem.
"""
import time
import requests
from satellite_engine.config import COPERNICUS_CLIENT_ID, COPERNICUS_CLIENT_SECRET, TOKEN_URL

_cached_token = None
_token_expiry = 0


def get_access_token():
    """
    Get a valid OAuth2 access token from Copernicus Data Space.
    Caches the token and auto-refreshes when expired.
    """
    global _cached_token, _token_expiry

    # Return cached token if still valid (with 60s buffer)
    if _cached_token and time.time() < _token_expiry - 60:
        return _cached_token

    if not COPERNICUS_CLIENT_ID or not COPERNICUS_CLIENT_SECRET:
        print("⚠️  No Copernicus credentials found. Set COPERNICUS_CLIENT_ID and COPERNICUS_CLIENT_SECRET in .env")
        return None

    data = {
        "grant_type": "client_credentials",
        "client_id": COPERNICUS_CLIENT_ID,
        "client_secret": COPERNICUS_CLIENT_SECRET,
    }

    try:
        response = requests.post(TOKEN_URL, data=data, timeout=15)
        if response.status_code == 200:
            token_data = response.json()
            _cached_token = token_data["access_token"]
            _token_expiry = time.time() + token_data.get("expires_in", 600)
            print("🔑 Copernicus token acquired successfully.")
            return _cached_token
        else:
            print(f"❌ Token request failed: {response.status_code} — {response.text[:200]}")
            return None
    except requests.RequestException as e:
        print(f"❌ Token request error: {e}")
        return None
