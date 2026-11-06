const defaultLocation = { lat: 9.0765, lng: 7.3986 };
let searchLocation = { ...defaultLocation };

const map = L.map("map").setView([defaultLocation.lat, defaultLocation.lng], 6);
L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    attribution: "© OpenStreetMap contributors"
}).addTo(map);

let stationMarkers = [];
let userMarker = null;
let reportTrigger = null;

const userIcon = L.icon({
    iconUrl: "https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-red.png",
    shadowUrl: "https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-shadow.png",
    iconSize: [25, 41],
    iconAnchor: [12, 41],
    popupAnchor: [1, -34],
    shadowSize: [41, 41]
});

const statusMessage = document.getElementById("statusMessage");
const stationList = document.getElementById("stationList");

function setStatus(message) {
    statusMessage.textContent = message;
}

function addText(parent, tagName, text, className = "") {
    const element = document.createElement(tagName);
    element.textContent = text;
    if (className) element.className = className;
    parent.appendChild(element);
    return element;
}

function makeReportButton(station, trigger) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "btn-small";
    button.textContent = "Report Price";
    button.addEventListener("click", (event) => {
        event.stopPropagation();
        window.openReport(station.id, station.name, trigger || button);
    });
    return button;
}

async function loadStations(lat, lng) {
    const nationwideSearch = document.getElementById("radiusFilter").value === "nearest";
    const params = new URLSearchParams({
        lat,
        lng,
        radius: document.getElementById("radiusFilter").value,
        fuel_type: document.getElementById("fuelFilter").value,
        brand: document.getElementById("brandFilter").value
    });

    try {
        const response = await fetch(`/api/stations/?${params}`);
        const stations = await response.json();
        if (!response.ok) {
            throw new Error(stations.error || "Could not load nearby stations.");
        }

        stationMarkers.forEach((marker) => map.removeLayer(marker));
        stationMarkers = [];
        stationList.replaceChildren();

        if (stations.length === 0) {
            addText(stationList, "p", "No stations are available in the station database yet.");
            setStatus("No stations found. Try a different fuel or brand filter.");
            return;
        }

        stations.forEach((station) => {
            const price = station.price
                ? `₦${station.price}/L`
                : "No price reported";
            const marker = L.marker([station.lat, station.lng]).addTo(map);
            const popup = document.createElement("div");
            addText(popup, "strong", station.name);
            addText(popup, "div", price);
            addText(popup, "div", `Queue: ${station.queue || "Unknown"}`);
            popup.appendChild(makeReportButton(station));
            marker.bindPopup(popup);
            stationMarkers.push(marker);

            const card = document.createElement("article");
            card.className = "station-card";
            const selectButton = document.createElement("button");
            selectButton.type = "button";
            selectButton.className = "station-select";
            selectButton.setAttribute(
                "aria-label",
                `Show ${station.name}, ${station.distance_km} kilometres away on the map`
            );
            const heading = document.createElement("div");
            addText(heading, "strong", station.name);
            if (station.brand) addText(heading, "span", station.brand, "badge");
            selectButton.appendChild(heading);

            const priceLine = document.createElement("div");
            priceLine.className = "station-price";
            addText(priceLine, "strong", price);
            addText(priceLine, "span", `${station.distance_km} km away`, "distance");
            selectButton.appendChild(priceLine);

            const queue = station.queue ? station.queue.replaceAll("_", " ") : "Unknown";
            const availability = station.available === null
                ? "Availability unknown"
                : station.available ? "Fuel available" : "Reported unavailable";
            const updated = station.updated ? ` · Updated ${station.updated}` : "";
            addText(selectButton, "p", `Queue: ${queue} · ${availability}${updated}`, "card-meta");
            selectButton.addEventListener("click", () => {
                map.setView([station.lat, station.lng], 15);
                marker.openPopup();
            });
            card.appendChild(selectButton);
            card.appendChild(makeReportButton(station));
            stationList.appendChild(card);
        });

        const searchPoints = stationMarkers.map((marker) => marker.getLatLng());
        searchPoints.push(L.latLng(lat, lng));
        if (userMarker) searchPoints.push(userMarker.getLatLng());
        map.fitBounds(L.latLngBounds(searchPoints).pad(0.1), { maxZoom: 13 });
        setStatus(nationwideSearch
            ? `Showing the ${stations.length} closest station${stations.length === 1 ? "" : "s"} in Nigeria, sorted by distance.`
            : `${stations.length} station${stations.length === 1 ? "" : "s"} found within ${document.getElementById("radiusFilter").value} km.`);
    } catch (error) {
        setStatus(error.message || "Unable to load stations. Check your connection and try again.");
    }
}

document.getElementById("locateBtn").addEventListener("click", () => {
    if (!navigator.geolocation) {
        setStatus("Location is not supported by this browser. You can still browse stations near Abuja.");
        return;
    }

    const button = document.getElementById("locateBtn");
    const originalText = button.textContent;
    button.disabled = true;
    button.textContent = "Locating…";
    setStatus("Getting your location…");

    navigator.geolocation.getCurrentPosition(
        ({ coords }) => {
            searchLocation = { lat: coords.latitude, lng: coords.longitude };
            if (userMarker) map.removeLayer(userMarker);
            userMarker = L.marker([coords.latitude, coords.longitude], { icon: userIcon })
                .addTo(map)
                .bindPopup("You are here");
            map.setView([coords.latitude, coords.longitude], 14);
            loadStations(coords.latitude, coords.longitude);
            button.disabled = false;
            button.textContent = originalText;
        },
        (error) => {
            const message = error.code === error.PERMISSION_DENIED
                ? "Location permission was denied. Allow location access in your browser settings, or browse stations near Abuja."
                : error.code === error.POSITION_UNAVAILABLE
                    ? "Your location is unavailable right now. Try again or browse stations near Abuja."
                    : "Finding your location took too long. Try again or browse stations near Abuja.";
            setStatus(message);
            button.disabled = false;
            button.textContent = originalText;
        },
        { enableHighAccuracy: true, timeout: 15000, maximumAge: 60000 }
    );
});

["fuelFilter", "brandFilter", "radiusFilter"].forEach((id) => {
    document.getElementById(id).addEventListener("change", () => {
        loadStations(searchLocation.lat, searchLocation.lng);
    });
});

window.openReport = function(stationId, stationName, trigger) {
    reportTrigger = trigger || document.activeElement;
    document.getElementById("reportStationId").value = stationId;
    document.getElementById("modalTitle").textContent = `Report Price: ${stationName}`;
    if (document.getElementById("fuelFilter").value) {
        document.getElementById("reportFuel").value =
            document.getElementById("fuelFilter").value;
    }
    document.getElementById("reportModal").classList.remove("hidden");
    document.getElementById("reportFuel").focus();
};

window.closeModal = function() {
    document.getElementById("reportModal").classList.add("hidden");
    document.getElementById("reportForm").reset();
    if (reportTrigger) reportTrigger.focus();
};

document.getElementById("closeReportModal").addEventListener("click", window.closeModal);
document.getElementById("reportModal").addEventListener("keydown", (event) => {
    if (event.key === "Escape") window.closeModal();
});

document.getElementById("reportForm").addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = event.currentTarget;
    const submitButton = form.querySelector('button[type="submit"]');
    submitButton.disabled = true;

    const body = {
        station_id: document.getElementById("reportStationId").value,
        fuel_type: document.getElementById("reportFuel").value,
        price: document.getElementById("reportPrice").value,
        queue_status: document.getElementById("reportQueue").value,
        is_available: document.getElementById("reportAvailable").checked
    };

    try {
        const response = await fetch("/api/report/", {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "X-CSRFToken": document.querySelector('meta[name="csrf-token"]').content
            },
            body: JSON.stringify(body)
        });
        const result = await response.json();
        if (!response.ok) throw new Error(result.error || "Could not submit your report.");

        window.closeModal();
        setStatus("Thank you — your price report helps other drivers.");
        loadStations(searchLocation.lat, searchLocation.lng);
    } catch (error) {
        setStatus(error.message || "Network error. Please try again.");
    } finally {
        submitButton.disabled = false;
    }
});

loadStations(searchLocation.lat, searchLocation.lng);

const offlineBanner = document.getElementById("offline-banner");
function updateOnlineStatus() {
    offlineBanner.style.display = navigator.onLine ? "none" : "block";
}
window.addEventListener("online", updateOnlineStatus);
window.addEventListener("offline", updateOnlineStatus);
updateOnlineStatus();
