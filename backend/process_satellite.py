import ee
import datetime
import requests

# 1. Initialize Earth Engine
ee.Initialize(project='thermal-sleuth')

def run_satellite_scan_and_push():
    print("🛰️ Starting Satellite Scan...")

    # --- EARTH ENGINE LOGIC ---
    roi = ee.Geometry.Polygon([[[23.58, 46.78], [23.65, 46.78], [23.65, 46.80], [23.58, 46.80]]])
    water_mask = ee.Image("JRC/GSW1_4/GlobalSurfaceWater").select('occurrence').gt(50)
    
    today = datetime.datetime.now()
    last_week = today - datetime.timedelta(days=7)

    recent_image = ee.ImageCollection('LANDSAT/LC09/C02/T1_L2') \
        .filterBounds(roi) \
        .filterDate(last_week.strftime('%Y-%m-%d'), today.strftime('%Y-%m-%d')) \
        .sort('system:time_start', False) \
        .first()

    if not recent_image:
        print("❌ No satellite images found for this week.")
        return

    # Extract temp and find anomalies
    current_temp = recent_image.select('ST_B10').multiply(0.00341802).add(149.0).subtract(273.15)
    current_temp = current_temp.updateMask(water_mask)
    anomalies = current_temp.gt(25) # Flagging water > 25°C

    # Convert to vectors
    anomaly_vectors = anomalies.selfMask().reduceToVectors(
        geometry=roi, scale=30, geometryType='centroid'
    )
    
    features = anomaly_vectors.getInfo()['features']
    print(f"✅ Found {len(features)} anomalies.")

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