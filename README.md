#  NaijaFuelFinder 🇳

**Find the nearest fuel stations, check real-time prices, and avoid long queues.**

NaijaFuelFinder is a crowdsourced, offline-capable Progressive Web App (PWA) designed specifically for Nigerian drivers. In a market where fuel prices fluctuate and queues can be unpredictable, this app provides real-time, community-driven data to help drivers make informed decisions.

---

##  Key Features

### 🗺️ Interactive Nationwide Map
- Powered by **Leaflet.js** and **OpenStreetMap**.
- Covers all 36 states + FCT with **1,300+ real fuel stations** imported directly from OpenStreetMap data.
- "Find Near Me" feature with custom red geolocation markers.

###  Real-Time Crowdsourced Data
- Users can report current fuel prices (PMS, AGO, LPG) and queue statuses.
- **Spam Protection:** Built-in 24-hour user limits and IP rate-limiting to prevent fake data.
- **Station Owner Portal:** Verified station owners can bypass limits to update their daily prices directly.

### 📱 Progressive Web App (PWA) & Offline Mode
- Fully installable on mobile home screens (Android & iOS).
- **Low-Data Mode:** Caches map tiles and API responses using Service Workers.
- Works seamlessly in areas with poor MTN/Airtel/Glo network coverage.
- Visual "Offline Banner" alerts users when they are viewing cached data.

###  Web Push Notifications
- Users can opt-in to receive real-time alerts.
- Notifies users instantly when a station nearby updates its price or gets fuel.

---

## ️ Tech Stack

- **Backend:** Python, Django
- **Database:** PostgreSQL (SQLite for local development)
- **Frontend:** HTML5, CSS3, Vanilla JavaScript
- **Maps:** Leaflet.js, OpenStreetMap, Overpass API
- **PWA:** Service Workers, Web App Manifest, VAPID (Web Push API)

---

## 🚀 Local Installation & Setup

Follow these steps to run NaijaFuelFinder on your local machine:

### 1. Clone the Repository
```bash
git clone https://github.com/YOUR_USERNAME/naija-fuel-finder.git
cd naija-fuel-finder