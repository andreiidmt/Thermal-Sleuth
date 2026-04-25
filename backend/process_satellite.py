import ee
import datetime
import requests

PROJECT_ID = 'thermal-sleuth'


def initialize_earth_engine():
    """Initialize Earth Engine and fail with a clear actionable message."""
    try:
        ee.Initialize(project=PROJECT_ID)
    except Exception as exc:
        raise RuntimeError(
            "Earth Engine initialization failed. Run 'earthengine authenticate' and verify "
            "internet access to earthengine.googleapis.com, then retry. "
            f"Original error: {exc}"
        ) from exc

def run_satellite_scan_and_push():
    print("🛰️ Starting Satellite Scan...")
    initialize_earth_engine()

    # --- EARTH ENGINE LOGIC ---
    # Citarum River area (West Java, Indonesia)
    roi = ee.Geometry.Polygon([[[106.55, -7.25], [107.95, -7.25], [107.95, -6.60], [106.55, -6.60]]])
    water_mask = ee.Image("JRC/GSW1_4/GlobalSurfaceWater").select('occurrence').gt(50)
    
    today = datetime.datetime.now()
    last_week = today - datetime.timedelta(days=720)

    collection = ee.ImageCollection('LANDSAT/LC09/C02/T1_L2') \
        .filterBounds(roi) \
        .filterDate(last_week.strftime('%Y-%m-%d'), today.strftime('%Y-%m-%d')) \
        .sort('system:time_start', False)

    image_count = collection.size().getInfo()
    print(f"🛰️ Images found in date range: {image_count}")
    if image_count == 0:
        print("❌ No satellite images found for this week.")
        return

    recent_image = ee.Image(collection.first())

    # Extract temp and find anomalies
    current_temp = recent_image.select('ST_B10').multiply(0.00341802).add(149.0).subtract(273.15)
    current_temp = current_temp.updateMask(water_mask)
    anomalies = current_temp.gt(25) # Flagging water > 25°C

    # Convert to vectors. The ROI is large, so enable bestEffort and raise maxPixels.
    anomaly_vectors = anomalies.selfMask().reduceToVectors(
        geometry=roi,
        scale=60,
        geometryType='centroid',
        bestEffort=True,
        maxPixels=1e13,
        tileScale=4
    )

    total_anomalies = anomaly_vectors.size().getInfo()
    print(f"✅ Found {total_anomalies} anomalies.")

    # Keep response manageable when bringing server-side EE data to local Python.
    max_features_to_push = 500
    features = anomaly_vectors.limit(max_features_to_push).getInfo().get('features', [])
    if total_anomalies > max_features_to_push:
        print(f"⚠️ Sending first {max_features_to_push} anomalies only (out of {total_anomalies}).")

    # --- PUSH TO COLLEAGUES' API ---
    TEAM_API_URL = "http://127.0.0.1:8000/anomalies/"

    for f in features:
        lon, lat = f['geometry']['coordinates']
        
        # This matches the format your colleague's API expects
        payload = {
            "name": "Sentinel-9 Anomaly",
            "lat": lat,
            "lon": lon,
            "temp_celsius": 32.5  # Static for demo, or you can extract real temp
        }
        
        try:
            response = requests.post(TEAM_API_URL, json=payload)
            if response.status_code == 200 or response.status_code == 201:
                print(f"🚀 Sent to Database: Lat {lat}, Lon {lon}")
            else:
                print(f"⚠️ API rejected data: {response.status_code} - {response.text}")
        except Exception as e:
            print(f"❌ Could not connect to colleagues' API: {e}")

if __name__ == "__main__":
    run_satellite_scan_and_push()