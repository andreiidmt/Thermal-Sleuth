"""
Thermal Sleuth — EU Industrial Facilities Database
Known thermal pollution sources for cross-referencing detected anomalies.
"""
import math

# Curated list of major EU industrial facilities near water bodies
# These are real facilities with real coordinates
EU_FACILITIES = [
    # ─── Romania ──────────────────────────────────────────────────
    {"name": "Turceni Thermal Power Plant", "lat": 44.6697, "lon": 23.3831,
     "type": "coal_power_plant", "country": "RO", "water_body": "Jiu River",
     "capacity_mw": 1650},
    {"name": "Rovinari Thermal Power Plant", "lat": 44.8483, "lon": 23.1647,
     "type": "coal_power_plant", "country": "RO", "water_body": "Jiu River",
     "capacity_mw": 1320},
    {"name": "Craiova II CET", "lat": 44.3269, "lon": 23.7947,
     "type": "coal_power_plant", "country": "RO", "water_body": "Jiu River",
     "capacity_mw": 600},
    {"name": "Iași CET", "lat": 47.1585, "lon": 27.5875,
     "type": "gas_power_plant", "country": "RO", "water_body": "Bahlui River",
     "capacity_mw": 250},
    {"name": "Brăila Thermal Power Plant", "lat": 45.2692, "lon": 27.9575,
     "type": "coal_power_plant", "country": "RO", "water_body": "Danube River",
     "capacity_mw": 315},
    {"name": "Galați Steel Works (ArcelorMittal)", "lat": 45.4353, "lon": 28.0078,
     "type": "steel_mill", "country": "RO", "water_body": "Danube River",
     "capacity_mw": 0},
    {"name": "Cernavodă Nuclear Power Plant", "lat": 44.3200, "lon": 28.0578,
     "type": "nuclear_power_plant", "country": "RO", "water_body": "Danube River",
     "capacity_mw": 1413},
    {"name": "Petrobrazi Refinery (OMV Petrom)", "lat": 44.9381, "lon": 25.9914,
     "type": "refinery", "country": "RO", "water_body": "Prahova River",
     "capacity_mw": 0},
    # ─── France ───────────────────────────────────────────────────
    {"name": "Gravelines Nuclear Power Plant", "lat": 51.0150, "lon": 2.1036,
     "type": "nuclear_power_plant", "country": "FR", "water_body": "North Sea Coast",
     "capacity_mw": 5460},
    {"name": "Tricastin Nuclear Power Plant", "lat": 44.3325, "lon": 4.7317,
     "type": "nuclear_power_plant", "country": "FR", "water_body": "Rhône River",
     "capacity_mw": 3660},
    {"name": "Bugey Nuclear Power Plant", "lat": 45.7983, "lon": 5.2706,
     "type": "nuclear_power_plant", "country": "FR", "water_body": "Rhône River",
     "capacity_mw": 3724},
    {"name": "Fos-sur-Mer Industrial Zone", "lat": 43.4350, "lon": 4.9400,
     "type": "steel_mill", "country": "FR", "water_body": "Mediterranean Coast",
     "capacity_mw": 0},
    # ─── Germany ──────────────────────────────────────────────────
    {"name": "Jänschwalde Power Plant", "lat": 51.8361, "lon": 14.4622,
     "type": "coal_power_plant", "country": "DE", "water_body": "Spree River",
     "capacity_mw": 3000},
    {"name": "Neurath Power Plant", "lat": 51.0547, "lon": 6.5992,
     "type": "coal_power_plant", "country": "DE", "water_body": "Rhine River",
     "capacity_mw": 4400},
    {"name": "Schwarze Pumpe Power Plant", "lat": 51.5361, "lon": 14.3525,
     "type": "coal_power_plant", "country": "DE", "water_body": "Spree River",
     "capacity_mw": 1600},
    {"name": "ThyssenKrupp Duisburg Steelworks", "lat": 51.4833, "lon": 6.7500,
     "type": "steel_mill", "country": "DE", "water_body": "Rhine River",
     "capacity_mw": 0},
    # ─── Italy ────────────────────────────────────────────────────
    {"name": "Brindisi Federico II Power Plant", "lat": 40.6181, "lon": 18.0042,
     "type": "coal_power_plant", "country": "IT", "water_body": "Adriatic Coast",
     "capacity_mw": 2640},
    {"name": "Taranto ILVA Steelworks", "lat": 40.4850, "lon": 17.2050,
     "type": "steel_mill", "country": "IT", "water_body": "Mar Grande",
     "capacity_mw": 0},
    {"name": "Porto Tolle Power Plant", "lat": 44.9658, "lon": 12.3467,
     "type": "gas_power_plant", "country": "IT", "water_body": "Po River Delta",
     "capacity_mw": 2640},
    {"name": "Civitavecchia Torrevaldaliga Power Plant", "lat": 42.1000, "lon": 11.7833,
     "type": "coal_power_plant", "country": "IT", "water_body": "Tyrrhenian Coast",
     "capacity_mw": 1980},
    # ─── Spain ────────────────────────────────────────────────────
    {"name": "Aboño Thermal Power Plant", "lat": 43.5550, "lon": -5.7000,
     "type": "coal_power_plant", "country": "ES", "water_body": "Aboño Estuary",
     "capacity_mw": 916},
    {"name": "As Pontes Power Plant", "lat": 43.4447, "lon": -7.8594,
     "type": "coal_power_plant", "country": "ES", "water_body": "Eume River",
     "capacity_mw": 1468},
    {"name": "Vandellòs Nuclear Power Plant", "lat": 41.1972, "lon": 0.8672,
     "type": "nuclear_power_plant", "country": "ES", "water_body": "Mediterranean Coast",
     "capacity_mw": 1087},
    # ─── Poland ───────────────────────────────────────────────────
    {"name": "Bełchatów Power Plant", "lat": 51.2636, "lon": 19.3192,
     "type": "coal_power_plant", "country": "PL", "water_body": "Widawka River",
     "capacity_mw": 5472},
    {"name": "Kozienice Power Plant", "lat": 51.5742, "lon": 21.5497,
     "type": "coal_power_plant", "country": "PL", "water_body": "Vistula River",
     "capacity_mw": 4070},
    {"name": "Połaniec Power Plant", "lat": 50.4342, "lon": 21.2831,
     "type": "coal_power_plant", "country": "PL", "water_body": "Vistula River",
     "capacity_mw": 1800},
    # ─── Netherlands ──────────────────────────────────────────────
    {"name": "Tata Steel IJmuiden", "lat": 52.4675, "lon": 4.6092,
     "type": "steel_mill", "country": "NL", "water_body": "North Sea Canal",
     "capacity_mw": 0},
    {"name": "Maasvlakte Power Plant", "lat": 51.9458, "lon": 4.0219,
     "type": "coal_power_plant", "country": "NL", "water_body": "North Sea Coast",
     "capacity_mw": 1100},
    # ─── Greece ───────────────────────────────────────────────────
    {"name": "Megalopoli Power Plant", "lat": 37.3953, "lon": 22.1278,
     "type": "coal_power_plant", "country": "GR", "water_body": "Alfeiós River",
     "capacity_mw": 850},
    # ─── Bulgaria ─────────────────────────────────────────────────
    {"name": "Maritsa Iztok-2 Power Plant", "lat": 42.1472, "lon": 25.9806,
     "type": "coal_power_plant", "country": "BG", "water_body": "Maritsa River",
     "capacity_mw": 1620},
    # ─── Czech Republic ──────────────────────────────────────────
    {"name": "Prunéřov Power Plant", "lat": 50.3911, "lon": 13.2747,
     "type": "coal_power_plant", "country": "CZ", "water_body": "Ohře River",
     "capacity_mw": 1490},
]


def haversine_km(lat1, lon1, lat2, lon2):
    """Calculate the great-circle distance between two points in km."""
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) ** 2 +
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
         math.sin(dlon / 2) ** 2)
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def find_nearest_facility(lat, lon, max_distance_km=10.0):
    """
    Find the nearest known industrial facility to the given coordinates.
    Returns the facility dict + distance, or None if nothing within range.
    """
    best = None
    best_dist = float("inf")

    for facility in EU_FACILITIES:
        dist = haversine_km(lat, lon, facility["lat"], facility["lon"])
        if dist < best_dist:
            best_dist = dist
            best = facility

    if best and best_dist <= max_distance_km:
        return {**best, "distance_km": round(best_dist, 2)}
    return None


def get_facilities_geojson():
    """Return all facilities as GeoJSON for the frontend map."""
    features = []
    for f in EU_FACILITIES:
        features.append({
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [f["lon"], f["lat"]]
            },
            "properties": {
                "name": f["name"],
                "type": f["type"],
                "country": f["country"],
                "water_body": f["water_body"],
                "capacity_mw": f["capacity_mw"],
            }
        })
    return {"type": "FeatureCollection", "features": features}
