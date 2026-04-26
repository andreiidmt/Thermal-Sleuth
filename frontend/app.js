// ==========================================
// 1. DATA STRUCTURE (Puncte de Alertă & Culori)
// ==========================================
const locationData = {
    "danube-steel": {
        name: "Danube River - Steel Plant Zone",
        camera: { center: [28.0333, 45.4333], zoom: 15.5, pitch: 60, bearing: -20 },
        synthesis: {
            cause: "Unregulated, high-volume coolant discharge from the primary heavy plate rolling mill.",
            severity: "Critical",
            severityClass: "severity-critical",
            impact: "Mass mortality of benthic invertebrates and alteration of migration routes for local sturgeon.",
            solution: "Mandate installation of closed-loop cooling towers."
        },
        dischargePoint: [28.0333, 45.4333],
        markerColor: '#ef4444' // Roșu pentru Critical
    },
    "olt-chemical": {
        name: "Olt River - Chemical Zone",
        camera: { center: [24.3667, 45.1000], zoom: 15.2, pitch: 65, bearing: 45 },
        synthesis: {
            cause: "Nighttime purging of high-temperature processing wastewater from synthetic fertilizer production lines.",
            severity: "High",
            severityClass: "severity-high",
            impact: "Accelerates toxic algal blooms, severely depleting dissolved oxygen.",
            solution: "Implement automated thermal shut-off valves at discharge pipes."
        },
        dischargePoint: [24.3667, 45.1000],
        markerColor: '#f97316' // Portocaliu pentru High
    }
};

const API_BASE_URL = 'http://127.0.0.1:8000';
let backendAnomalyFeatures = [];
let dropdownAnomalyFeatures = [];
let selectedZoneFeature = null;
let anomalyRefreshTimer = null;
let isLoadingAnomalies = false;
const ANOMALY_REFRESH_INTERVAL_MS = 10000;
const DROPDOWN_CLUSTER_RADIUS_KM = 5;
const MAX_DROPDOWN_ANOMALY_GROUPS = 50;

// ==========================================
// 2. MAPBOX INITIALIZATION
// ==========================================
// TODO: Pune token-ul tău de la Mapbox aici (păstrează ghilimelele!)
mapboxgl.accessToken = 'pk.eyJ1IjoiYW5kcmFhYTQ3IiwiYSI6ImNtb2U3aWR1YzBmYTkycnIzemQ3bnM4bmMifQ.69LxaNB6Iim7lpVNCOTz2w';

const map = new mapboxgl.Map({
    container: 'map',
    style: 'mapbox://styles/mapbox/dark-v11',
    center: [15.0, 50.0], // Europe-wide monitoring view
    zoom: 4,
    pitch: 0,
    antialias: true,
    projection: 'globe'
});

// Atmosferă pentru modul Globe
map.on('style.load', () => {
    map.setFog({
        'color': '#a855f7',
        'high-color': '#0ea5e9',
        'space-color': '#110c24',
        'star-intensity': 1.0
    });
});

// ==========================================
// 3. SATELLITE ANIMATION LOGIC
// ==========================================
let satellites = [];
const NUM_SATELLITES = 25;

for (let i = 0; i < NUM_SATELLITES; i++) {
    satellites.push({
        lng: (Math.random() - 0.5) * 360,
        lat: (Math.random() - 0.5) * 160,
        dlng: (Math.random() > 0.5 ? 1 : -1) * ((Math.random() * 0.02) + 0.01),
        dlat: (Math.random() > 0.5 ? 1 : -1) * ((Math.random() * 0.02) + 0.01)
    });
}

function getSatelliteGeoJSON() {
    return {
        type: 'FeatureCollection',
        features: satellites.map(sat => ({
            type: 'Feature',
            geometry: { type: 'Point', coordinates: [sat.lng, sat.lat] }
        }))
    };
}

function animateSatellites() {
    satellites.forEach(sat => {
        sat.lng += sat.dlng; sat.lat += sat.dlat;
        if (sat.lng > 180) sat.lng -= 360; else if (sat.lng < -180) sat.lng += 360;
        if (sat.lat > 90) sat.lat -= 180; else if (sat.lat < -90) sat.lat += 180;
    });

    if (map.getSource('satellites')) {
        map.getSource('satellites').setData(getSatelliteGeoJSON());
    }
    requestAnimationFrame(animateSatellites); // Animația va rula la nesfârșit acum!
}

// ==========================================
// 4. MAP LAYERS & MARKERS
// ==========================================
map.on('load', () => {

    // --- ADAUGAM SATELITII INAPOI ---
    map.addSource('satellites', { type: 'geojson', data: getSatelliteGeoJSON() });
    map.addLayer({
        id: 'satellite-glow', type: 'circle', source: 'satellites',
        paint: { 'circle-radius': 10, 'circle-color': '#c084fc', 'circle-opacity': 0.6, 'circle-blur': 1 }
    });
    map.addLayer({
        id: 'satellite-core', type: 'circle', source: 'satellites',
        paint: { 'circle-radius': 3, 'circle-color': '#ffffff' }
    });
    animateSatellites(); // Pornim animația

    // EVIDENȚIERE GLOBALĂ A APELOR
    map.setPaintProperty('water', 'fill-color', '#1e3a8a');
    map.setPaintProperty('waterway', 'line-color', '#3b82f6');
    map.setPaintProperty('waterway', 'line-width', 2);

    // CLĂDIRI 3D
    map.addLayer({
        'id': '3d-buildings',
        'source': 'composite',
        'source-layer': 'building',
        'filter': ['==', 'extrude', 'true'],
        'type': 'fill-extrusion',
        'minzoom': 14,
        'paint': {
            'fill-extrusion-color': '#1e293b',
            'fill-extrusion-height': ['get', 'height'],
            'fill-extrusion-base': ['get', 'min_height'],
            'fill-extrusion-opacity': 0.7
        }
    });

    // SISTEMUL DE ALERTĂ
    map.addSource('anomaly-marker', {
        type: 'geojson',
        data: { type: 'FeatureCollection', features: [] }
    });

    // Aura difuză
    map.addLayer({
        id: 'anomaly-glow',
        type: 'circle',
        source: 'anomaly-marker',
        paint: {
            'circle-radius': ['interpolate', ['linear'], ['zoom'], 10, 20, 16, 70],
            'circle-blur': 0.8,
            'circle-color': ['get', 'color'],
            'circle-opacity': 0.7
        }
    });

    // Nucleul alertelor
    map.addLayer({
        id: 'anomaly-core',
        type: 'circle',
        source: 'anomaly-marker',
        paint: {
            'circle-radius': ['interpolate', ['linear'], ['zoom'], 10, 10, 16, 25],
            'circle-color': ['get', 'color'],
            'circle-opacity': 0.9,
            'circle-stroke-width': 3,
            'circle-stroke-color': '#000000'
        }
    });

    // Semnul !
    map.addLayer({
        id: 'anomaly-symbol',
        type: 'symbol',
        source: 'anomaly-marker',
        layout: {
            'text-field': '!',
            'text-size': ['interpolate', ['linear'], ['zoom'], 10, 16, 16, 28],
            'text-font': ['Open Sans Bold', 'Arial Unicode MS Bold'],
            'text-allow-overlap': true
        },
        paint: {
            'text-color': '#ffffff'
        }
    });

    populateDropdown();
    loadAnomaliesFromBackend();
    startAnomalyAutoRefresh();

    map.on('click', 'anomaly-core', (event) => {
        const feature = event.features && event.features[0];
        if (!feature) return;

        const coordinates = feature.geometry.coordinates.slice();
        const props = feature.properties || {};
        const popupHtml = `
            <strong>${props.name || 'Thermal anomaly'}</strong><br>
            Temperature: ${props.temp_celsius || 'N/A'} °C<br>
            Severity: ${props.severity || 'N/A'}
        `;

        new mapboxgl.Popup()
            .setLngLat(coordinates)
            .setHTML(popupHtml)
            .addTo(map);
    });

    map.on('mouseenter', 'anomaly-core', () => {
        map.getCanvas().style.cursor = 'pointer';
    });

    map.on('mouseleave', 'anomaly-core', () => {
        map.getCanvas().style.cursor = '';
    });
});

// ==========================================
// 5. UI INTERACTIVITY
// ==========================================
const selectEl = document.getElementById('location-select');
const synthesisPanel = document.getElementById('synthesis-panel');

function populateDropdown() {
    Object.keys(locationData).forEach(key => {
        const option = document.createElement('option');
        option.value = key;
        option.textContent = locationData[key].name;
        selectEl.appendChild(option);
    });
}

function populateDropdownWithAnomalies() {
    // Remove old anomaly options (keep only predefined locations)
    const options = Array.from(selectEl.querySelectorAll('option'));
    options.forEach(opt => {
        if (opt.value.startsWith('anomaly-')) {
            opt.remove();
        }
    });

    dropdownAnomalyFeatures = clusterAnomalyFeaturesForDropdown(backendAnomalyFeatures, DROPDOWN_CLUSTER_RADIUS_KM);

    // Add clustered anomaly groups as options (up to 50 to avoid huge list)
    dropdownAnomalyFeatures.slice(0, MAX_DROPDOWN_ANOMALY_GROUPS).forEach((feature, index) => {
        const option = document.createElement('option');
        option.value = `anomaly-cluster-${index}`;

        const props = feature.properties || {};
        const clusterSize = props.cluster_size || 1;
        const clusterTemp = props.max_temp_celsius !== 'N/A' ? ` (${props.max_temp_celsius}°C)` : '';
        const clusterSuffix = clusterSize > 1
            ? ` - ${clusterSize} detections in ${DROPDOWN_CLUSTER_RADIUS_KM}km`
            : '';

        option.textContent = `${props.name}${clusterTemp}${clusterSuffix}`;
        selectEl.appendChild(option);
    });

    if (dropdownAnomalyFeatures.length > MAX_DROPDOWN_ANOMALY_GROUPS) {
        const option = document.createElement('option');
        option.value = '';
        option.textContent = `... and ${dropdownAnomalyFeatures.length - MAX_DROPDOWN_ANOMALY_GROUPS} more anomaly groups`;
        option.disabled = true;
        selectEl.appendChild(option);
    }
}

function generateMarkerGeoJSON(coords, color) {
    return {
        type: 'Feature',
        properties: { color: color, name: 'Selected monitoring zone', severity: 'Manual' },
        geometry: { type: 'Point', coordinates: coords }
    };
}

function getSeverityFromTemp(tempCelsius) {
    if (tempCelsius >= 38) return { level: 'Critical', color: '#ef4444' };
    if (tempCelsius >= 34) return { level: 'High', color: '#f97316' };
    if (tempCelsius >= 30) return { level: 'Moderate', color: '#eab308' };
    return { level: 'Low', color: '#22c55e' };
}

function toRadians(degrees) {
    return (degrees * Math.PI) / 180;
}

function haversineDistanceKm(coordA, coordB) {
    if (!Array.isArray(coordA) || !Array.isArray(coordB)) return Number.POSITIVE_INFINITY;

    const [lon1, lat1] = coordA;
    const [lon2, lat2] = coordB;
    const earthRadiusKm = 6371;

    const dLat = toRadians(lat2 - lat1);
    const dLon = toRadians(lon2 - lon1);

    const a =
        Math.sin(dLat / 2) * Math.sin(dLat / 2) +
        Math.cos(toRadians(lat1)) * Math.cos(toRadians(lat2)) *
        Math.sin(dLon / 2) * Math.sin(dLon / 2);

    const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
    return earthRadiusKm * c;
}

function getNumericTemperature(value) {
    const numericValue = Number(value);
    return Number.isFinite(numericValue) ? numericValue : null;
}

function clusterAnomalyFeaturesForDropdown(features, radiusKm) {
    if (!Array.isArray(features) || features.length === 0) {
        return [];
    }

    const visited = new Array(features.length).fill(false);
    const clusters = [];

    for (let i = 0; i < features.length; i++) {
        if (visited[i]) continue;

        const queue = [i];
        const memberIndexes = [];
        visited[i] = true;

        while (queue.length > 0) {
            const currentIndex = queue.shift();
            memberIndexes.push(currentIndex);

            for (let j = 0; j < features.length; j++) {
                if (visited[j]) continue;

                const distanceKm = haversineDistanceKm(
                    features[currentIndex]?.geometry?.coordinates,
                    features[j]?.geometry?.coordinates
                );

                if (distanceKm <= radiusKm) {
                    visited[j] = true;
                    queue.push(j);
                }
            }
        }

        const members = memberIndexes.map(index => features[index]);

        const representative = members.reduce((best, current) => {
            if (!best) return current;

            const bestTemp = getNumericTemperature(best.properties?.temp_celsius);
            const currentTemp = getNumericTemperature(current.properties?.temp_celsius);

            if (currentTemp === null) return best;
            if (bestTemp === null) return current;
            return currentTemp > bestTemp ? current : best;
        }, null) || members[0];

        const maxClusterTemp = members.reduce((maxTemp, feature) => {
            const temp = getNumericTemperature(feature.properties?.temp_celsius);
            if (temp === null) return maxTemp;
            return Math.max(maxTemp, temp);
        }, Number.NEGATIVE_INFINITY);

        const clusterSize = members.length;
        const representativeName = representative.properties?.name || 'Thermal anomaly';

        clusters.push({
            ...representative,
            properties: {
                ...representative.properties,
                name: clusterSize > 1 ? `Thermal anomaly cluster near ${representativeName}` : representativeName,
                cluster_size: clusterSize,
                max_temp_celsius: maxClusterTemp === Number.NEGATIVE_INFINITY
                    ? 'N/A'
                    : Number(maxClusterTemp.toFixed(1)),
                cluster_radius_km: radiusKm
            }
        });
    }

    clusters.sort((a, b) => {
        const sizeDiff = (b.properties?.cluster_size || 1) - (a.properties?.cluster_size || 1);
        if (sizeDiff !== 0) return sizeDiff;

        const aTemp = getNumericTemperature(a.properties?.max_temp_celsius);
        const bTemp = getNumericTemperature(b.properties?.max_temp_celsius);
        if (aTemp === null && bTemp === null) return 0;
        if (aTemp === null) return 1;
        if (bTemp === null) return -1;
        return bTemp - aTemp;
    });

    return clusters;
}

function renderAnomalySource() {
    const source = map.getSource('anomaly-marker');
    if (!source) {
        console.warn('[renderAnomalySource] anomaly-marker source not found on map');
        return;
    }

    const features = [...backendAnomalyFeatures];
    if (selectedZoneFeature) features.push(selectedZoneFeature);

    console.log(`[${new Date().toLocaleTimeString()}] Rendering ${features.length} total features on map`);
    source.setData({
        type: 'FeatureCollection',
        features
    });
}

async function loadAnomaliesFromBackend() {
    if (isLoadingAnomalies) return;
    isLoadingAnomalies = true;

    try {
        console.log(`[${new Date().toLocaleTimeString()}] Fetching anomalies from ${API_BASE_URL}/anomalies/`);
        const response = await fetch(`${API_BASE_URL}/anomalies/`);
        if (!response.ok) {
            throw new Error(`Backend returned HTTP ${response.status}`);
        }

        const anomalies = await response.json();
        console.log(`[${new Date().toLocaleTimeString()}] Received ${anomalies.length} anomalies from backend`);
        if (!Array.isArray(anomalies)) {
            throw new Error('Unexpected payload received from backend.');
        }

        backendAnomalyFeatures = anomalies.map((anomaly) => {
            const severity = getSeverityFromTemp(anomaly.temp_celsius);
            return {
                type: 'Feature',
                properties: {
                    color: severity.color,
                    severity: severity.level,
                    name: anomaly.name,
                    temp_celsius: anomaly.temp_celsius
                },
                geometry: {
                    type: 'Point',
                    coordinates: [anomaly.lon, anomaly.lat]
                }
            };
        });

        if (backendAnomalyFeatures.length === 0) {
            backendAnomalyFeatures = Object.values(locationData).map((zone) => ({
                type: 'Feature',
                properties: {
                    color: zone.markerColor,
                    severity: zone.synthesis.severity,
                    name: zone.name,
                    temp_celsius: 'N/A'
                },
                geometry: {
                    type: 'Point',
                    coordinates: zone.dischargePoint
                }
            }));
        }

        renderAnomalySource();
        populateDropdownWithAnomalies();
    } catch (error) {
        console.error(`[${new Date().toLocaleTimeString()}] Failed to load anomalies from backend:`, error.message);
        backendAnomalyFeatures = Object.values(locationData).map((zone) => ({
            type: 'Feature',
            properties: {
                color: zone.markerColor,
                severity: zone.synthesis.severity,
                name: zone.name,
                temp_celsius: 'N/A'
            },
            geometry: {
                type: 'Point',
                coordinates: zone.dischargePoint
            }
        }));
        renderAnomalySource();
        populateDropdownWithAnomalies();
    } finally {
        isLoadingAnomalies = false;
    }
}

function startAnomalyAutoRefresh() {
    console.log(`[${new Date().toLocaleTimeString()}] Starting auto-refresh polling every ${ANOMALY_REFRESH_INTERVAL_MS}ms`);
    if (anomalyRefreshTimer) clearInterval(anomalyRefreshTimer);

    anomalyRefreshTimer = setInterval(() => {
        loadAnomaliesFromBackend();
    }, ANOMALY_REFRESH_INTERVAL_MS);

    document.addEventListener('visibilitychange', () => {
        if (!document.hidden) {
            console.log(`[${new Date().toLocaleTimeString()}] Page became visible, refreshing anomalies`);
            loadAnomaliesFromBackend();
        }
    });
}

selectEl.addEventListener('change', (e) => {
    const targetKey = e.target.value;
    
    // Check if it's a predefined location
    if (locationData[targetKey]) {
        const data = locationData[targetKey];

        document.getElementById('cause-text').textContent = data.synthesis.cause;
        document.getElementById('impact-text').textContent = data.synthesis.impact;
        document.getElementById('solution-text').textContent = data.synthesis.solution;

        const badge = document.getElementById('severity-badge');
        badge.textContent = data.synthesis.severity;
        badge.className = `badge ${data.synthesis.severityClass}`;

        synthesisPanel.classList.remove('hidden');

        map.flyTo({
            ...data.camera,
            essential: true,
            duration: 3500,
            curve: 1.2
        });

        setTimeout(() => {
            selectedZoneFeature = generateMarkerGeoJSON(data.dischargePoint, data.markerColor);
            renderAnomalySource();
        }, 2000);
    } 
    // Check if it's a satellite-detected anomaly
    else if (targetKey.startsWith('anomaly-cluster-')) {
        const anomalyIndex = parseInt(targetKey.split('-')[2], 10);
        const anomaly = dropdownAnomalyFeatures[anomalyIndex];
        
        if (!anomaly) return;

        const coords = anomaly.geometry.coordinates;
        const props = anomaly.properties;
        const clusterSize = props.cluster_size || 1;
        
        // Show anomaly details in synthesis panel
        document.getElementById('cause-text').textContent = clusterSize > 1
            ? `Clustered thermal anomaly (${clusterSize} detections within ${DROPDOWN_CLUSTER_RADIUS_KM} km)`
            : 'Satellite-detected thermal anomaly';
        document.getElementById('impact-text').textContent = `Location: ${coords[0].toFixed(4)}, ${coords[1].toFixed(4)}`;

        if (clusterSize > 1) {
            document.getElementById('solution-text').textContent = `Cluster max temperature: ${props.max_temp_celsius}°C`;
        } else {
            document.getElementById('solution-text').textContent = `Temperature: ${props.temp_celsius}°C`;
        }

        const badge = document.getElementById('severity-badge');
        badge.textContent = props.severity;
        badge.className = `badge severity-${props.severity.toLowerCase()}`;

        synthesisPanel.classList.remove('hidden');

        // Fly to anomaly
        map.flyTo({
            center: coords,
            zoom: 14,
            essential: true,
            duration: 2000,
            pitch: 45,
            bearing: 0
        });
    }
});
