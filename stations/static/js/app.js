// 1. Initialize the map centered on Abuja
const map = L.map('map').setView([9.0765, 7.3986], 6); 
L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    attribution: '© OpenStreetMap contributors'
}).addTo(map);

let markers = [];

// Custom Red Icon for User Location
const userIcon = L.icon({
    iconUrl: 'https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-red.png',
    shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-shadow.png',
    iconSize: [25, 41],
    iconAnchor: [12, 41],
    popupAnchor: [1, -34],
    shadowSize: [41, 41]
});

let userMarker = null; // This will hold the user's red marker

// 2. Function to fetch and display stations
async function loadStations(lat, lng) {
    const fuel = document.getElementById('fuelFilter').value;
    const brand = document.getElementById('brandFilter').value;
    
    const params = new URLSearchParams({ 
        lat: lat, 
        lng: lng, 
        radius: 50, 
        fuel_type: fuel, 
        brand: brand 
    });

    try {
        const res = await fetch(`/api/stations/?${params}`);
        const stations = await res.json();

        markers.forEach(m => map.removeLayer(m));
        markers = [];
        
        const listEl = document.getElementById('stationList');
        listEl.innerHTML = '';

        if (stations.length === 0) {
            listEl.innerHTML = '<p style="text-align:center; color:#6b7280;">No stations found in this area.</p>';
            return;
        }

        stations.forEach(s => {
            const marker = L.marker([s.lat, s.lng]).addTo(map);
            const priceStr = s.price ? `₦${s.price}/L` : 'No recent report';
            
            marker.bindPopup(`
                <strong>${s.name}</strong><br>
                ${priceStr}<br>
                Queue: ${s.queue || 'Unknown'}<br>
                <button class="btn-small" onclick="openReport(${s.id}, '${s.name.replace(/'/g, "\\'")}')">📝 Report Price</button>
            `);
            markers.push(marker);

            const card = document.createElement('div');
            card.className = 'station-card';
            card.innerHTML = `
                <div><strong>${s.name}</strong><span class="badge">${s.brand}</span></div>
                <div style="margin-top:4px; font-size:1.1rem; color:#059669; font-weight:bold;">${priceStr} <span style="font-size:0.8rem; color:#6b7280; font-weight:normal;">· ${s.distance_km}km away</span></div>
                <div class="card-meta">Queue: ${s.queue || '?'} · Updated: ${s.updated || 'Never'}</div>
                <button class="btn-small" onclick="openReport(${s.id}, '${s.name.replace(/'/g, "\\'")}')">Report Price</button>
            `;
            
            card.addEventListener('click', (e) => {
                if (e.target.tagName !== 'BUTTON') {
                    map.setView([s.lat, s.lng], 15); 
                    marker.openPopup();
                }
            });
            listEl.appendChild(card);
        });
        
        if (markers.length > 0) {
            const group = L.featureGroup(markers);
            map.fitBounds(group.getBounds().pad(0.1));
        }

    } catch (error) {
        console.error('Error loading stations:', error);
    }
}

// 3. Geolocation Button (With Red Marker)
document.getElementById('locateBtn').addEventListener('click', () => {
    if (!navigator.geolocation) {
        alert('Geolocation is not supported by your browser.');
        return;
    }
    
    const btn = document.getElementById('locateBtn');
    const originalText = btn.textContent;
    btn.textContent = '📍 Locating...';
    
    navigator.geolocation.getCurrentPosition(
        pos => { 
            const lat = pos.coords.latitude;
            const lng = pos.coords.longitude;
            
            // Remove old user marker if it exists
            if (userMarker) {
                map.removeLayer(userMarker);
            }

            // Add the new Red Marker for the user
            userMarker = L.marker([lat, lng], { icon: userIcon })
                .addTo(map)
                .bindPopup("<b>📍 You are here!</b>")
                .openPopup();

            map.setView([lat, lng], 14); 
            loadStations(lat, lng); 
            
            btn.textContent = originalText;
        },
        () => {
            alert('Location access denied. Please allow location access to find stations near you.');
            btn.textContent = originalText;
        }
    );
});

// 4. Filter Change Listeners
['fuelFilter', 'brandFilter'].forEach(id => {
    document.getElementById(id).addEventListener('change', () => {
        const center = map.getCenter();
        loadStations(center.lat, center.lng);
    });
});

// 5. Modal Logic
window.openReport = function(stationId, stationName) {
    document.getElementById('reportStationId').value = stationId;
    document.getElementById('modalTitle').textContent = `Report Price: ${stationName}`;
    document.getElementById('reportModal').classList.remove('hidden');
};

window.closeModal = function() {
    document.getElementById('reportModal').classList.add('hidden');
    document.getElementById('reportForm').reset();
};

// 6. Form Submission
document.getElementById('reportForm').addEventListener('submit', async (e) => {
    e.preventDefault();
    
    const body = {
        station_id: document.getElementById('reportStationId').value,
        fuel_type: document.getElementById('reportFuel').value,
        price: document.getElementById('reportPrice').value,
        queue_status: document.getElementById('reportQueue').value,
        is_available: document.getElementById('reportAvailable').checked
    };

    try {
        const res = await fetch('/api/report/', { 
            method: 'POST', 
            headers: { 'Content-Type': 'application/json' }, 
            body: JSON.stringify(body) 
        });
        
        if (res.ok) { 
            alert('Thank you! Your report helps other Nigerians.'); 
            closeModal(); 
            const c = map.getCenter(); 
            loadStations(c.lat, c.lng); 
        } else { 
            const err = await res.json(); 
            alert('Error submitting report: ' + err.error); 
        }
    } catch (error) {
        alert('Network error. Please try again.');
    }
});

// 7. Initial Load
loadStations(9.0765, 7.3986);

// --- OFFLINE / LOW DATA MODE LOGIC ---
const offlineBanner = document.getElementById('offline-banner');

function updateOnlineStatus() {
    if (navigator.onLine) {
        offlineBanner.style.display = 'none';
    } else {
        offlineBanner.style.display = 'block';
    }
}

window.addEventListener('online', updateOnlineStatus);
window.addEventListener('offline', updateOnlineStatus);
updateOnlineStatus();

// --- PUSH NOTIFICATION LOGIC ---
function urlBase64ToUint8Array(base64String) {
  const padding = '='.repeat((4 - base64String.length % 4) % 4);
  const base64 = (base64String + padding).replace(/\-/g, '+').replace(/_/g, '/');
  const rawData = window.atob(base64);
  const outputArray = new Uint8Array(rawData.length);
  for (let i = 0; i < rawData.length; ++i) {
    outputArray[i] = rawData.charCodeAt(i);
  }
  return outputArray;
}

async function enableAlerts() {
  const btn = document.getElementById('enableAlertsBtn');
  if (!btn) return console.log("Alerts button not found");
  
  console.log("1. Button found. Getting Service Worker...");
  const reg = await navigator.serviceWorker.ready;
  
  console.log("2. Requesting permission...");
  const sub = await reg.pushManager.subscribe({
    userVisibleOnly: true,
    // Your actual public key is inserted here
    applicationServerKey: urlBase64ToUint8Array("BKsa4tyJhQBcuhzBvu8Kwb_iF4cGCos04K0Y8sgdPj_XKl97N3-e3uXbMTR1BmNyY4Ysn3q3GnzkW-qU9zBuv3U")
  });
  
  console.log("3. Subscription created! Saving to backend...");
  await fetch('/api/save-subscription/', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify(sub.toJSON())
  });
  
  btn.textContent = '✅ Alerts Enabled';
  btn.style.background = '#059669';
  btn.style.color = 'white';
  btn.style.borderColor = '#059669';
  console.log("4. DONE! Button is now green.");
}

const enableAlertsBtn = document.getElementById('enableAlertsBtn');
if (enableAlertsBtn) {
    enableAlertsBtn.addEventListener('click', enableAlerts);
}