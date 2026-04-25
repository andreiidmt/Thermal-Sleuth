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

// ==========================================
// 2. MAPBOX INITIALIZATION
// ==========================================
// TODO: Pune token-ul tău de la Mapbox aici (păstrează ghilimelele!)
mapboxgl.accessToken = 'pk.eyJ1IjoiYW5kcmFhYTQ3IiwiYSI6ImNtb2U3aWR1YzBmYTkycnIzemQ3bnM4bmMifQ.69LxaNB6Iim7lpVNCOTz2w';

const map = new mapboxgl.Map({
    container: 'map',
    style: 'mapbox://styles/mapbox/dark-v11',
    center: [25.0, 45.0], // Centrat pe România
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

function generateMarkerGeoJSON(coords, color) {
    return {
        type: 'FeatureCollection',
        features: [{
            type: 'Feature',
            properties: { color: color },
            geometry: { type: 'Point', coordinates: coords }
        }]
    };
}

selectEl.addEventListener('change', (e) => {
    const targetKey = e.target.value;
    const data = locationData[targetKey];

    if (!data) return;

    // AI AICI ERA CODUL CARE OPRA SATELITII. A FOST STERS.

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
        const geojson = generateMarkerGeoJSON(data.dischargePoint, data.markerColor);
        map.getSource('anomaly-marker').setData(geojson);
    }, 2000);
});
