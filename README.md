#  NaijaFuelFinder 🇳

**Find the nearest fuel stations, check real-time prices, and avoid long queues.**

NaijaFuelFinder is a crowdsourced, offline-capable Progressive Web App (PWA) designed specifically for Nigerian drivers. In a market where fuel prices fluctuate and queues can be unpredictable, this app provides real-time, community-driven data to help drivers make informed decisions.

---

##  Key Features

### 🗺️ Interactive Nationwide Map
- Powered by **MapLibre GL JS** and **OpenFreeMap** vector tiles, with no API key required.
- Covers all 36 states + FCT with **1,300+ real fuel stations** imported directly from OpenStreetMap data.
- "Find Near Me" feature that searches around the driver's location anywhere in Nigeria.
- Map and distance-sorted list of nearby stations, with a nationwide option for the ten closest stations.

###  Real-Time Crowdsourced Data
- Users can report current fuel prices (PMS, AGO, LPG) and queue statuses.
- **Spam Protection:** Built-in 24-hour user limits and IP rate-limiting to prevent fake data.
- **Station Owner Portal:** Verified station owners can bypass limits to update their daily prices directly.

### 📱 Progressive Web App (PWA)
- Fully installable on mobile home screens (Android & iOS).
- Caches app files and station API responses using a Service Worker.
- Shows an offline banner when the network is unavailable; live map tiles require an internet connection.

### Planned: Web Push Notifications
- Push alerts are not available yet. Station prices and availability are currently shared through driver reports.

---

## ️ Tech Stack

- **Backend:** Python, Django
- **Database:** PostgreSQL (SQLite for local development)
- **Frontend:** HTML5, CSS3, Vanilla JavaScript
- **Maps:** MapLibre GL JS with OpenFreeMap vector tiles, Overpass API
- **PWA:** Service Workers, Web App Manifest

---

## 🚀 Local Installation & Setup

Follow these steps to run NaijaFuelFinder on your local machine:

### 1. Clone the Repository
```
git clone https://github.com/kingsley60/naija_fuel_finder.git
cd naija_fuel_finder
```

### 2. Install dependencies
```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
export DJANGO_DEBUG=true
```

### 3. Prepare the database and start the app
```bash
python manage.py migrate
python import_osm_json.py
python manage.py runserver
```

The bundled OSM snapshot is imported into the database after migrations. To refresh from the live OpenStreetMap Overpass service instead, run `python import_stations.py`. It fetches Nigeria in smaller regions, tries alternate Overpass endpoints, and subdivides timed-out regions further. Stations fetched successfully are retained if some smallest regions remain unavailable; a partial import exits with an error and identifies the failed regions. To retry only region 4 with a 20-second per-endpoint timeout, run `python -u import_stations.py --regions 4 --timeout 20`; region numbers are the `[n/25]` numbers printed during import. The default import timeout is longer and the full import can take several minutes depending on Overpass availability. The app uses SQLite by default for local development. To use PostgreSQL, set `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_HOST`, and `POSTGRES_PORT` in the environment before starting Django.

Use **Find Near Me** to search around your current location. Choose a distance to see stations in that radius, or **Closest 10 in Nigeria** to find the nearest stations across the imported station dataset. Selecting a result focuses the map on that station. Location access requires HTTPS in production; browsers allow it on `localhost` during development. Price reports require an account, and station prices are community-submitted rather than guaranteed real-time.

The map uses OpenFreeMap's MapLibre style and does not require an API key. The style and tiles need an internet connection. Review OpenFreeMap's current usage terms before production use, and use a provider or hosting plan appropriate for your traffic.

## Production deployment

Set these environment variables in your hosting provider's secret/configuration manager. Do not commit production secrets or put real credentials in this file:

```text
DJANGO_DEBUG=false
DJANGO_SECRET_KEY=<new randomly generated Django secret>
DJANGO_ALLOWED_HOSTS=fuel.example.com
CSRF_TRUSTED_ORIGINS=https://fuel.example.com
POSTGRES_DB=<database name>
POSTGRES_USER=<database user>
POSTGRES_PASSWORD=<database password>
POSTGRES_HOST=<database host>
POSTGRES_PORT=5432
EMAIL_HOST=<SMTP server>
EMAIL_PORT=587
EMAIL_HOST_USER=<SMTP username>
EMAIL_HOST_PASSWORD=<SMTP password>
EMAIL_USE_TLS=true
DEFAULT_FROM_EMAIL=NaijaFuelFinder <noreply@fuel.example.com>
```

Terminate HTTPS at your hosting provider or reverse proxy before deploying with these settings. Only set `USE_X_FORWARDED_PROTO=true` if a trusted proxy overwrites the `X-Forwarded-Proto` header. Keep HSTS enabled only when the domain is reliably HTTPS; do not enable HSTS preload or include subdomains unless all affected hosts support HTTPS.

Before serving traffic, run:

```bash
python manage.py check --deploy
python manage.py migrate
python manage.py collectstatic --noinput
```

Configure the web server/CDN to serve files from `staticfiles/`, and back up the production database. Rotate any Django or push-notification secrets that have ever been committed or shared; removing a secret from the current file does not erase it from Git history.

## Updating the PythonAnywhere site

The public site only changes after the updated code is pushed to the branch PythonAnywhere uses and the web app is reloaded. This repository's GitHub URL is `https://github.com/kingsley60/naija_fuel_finder.git`.

### 1. Push your reviewed local changes

Review the changed files first so you do not include unrelated work. Then stage the application changes, commit them, and push the branch configured on PythonAnywhere (currently `main`):

```bash
git status --short
git add .gitignore README.md config import_osm_json.py import_stations.py manage.py requirements.txt stations users
git diff --cached --check
git commit -m "Prepare NaijaFuelFinder for PythonAnywhere"
git push origin main
```

### 2. Pull the code on PythonAnywhere

Open a PythonAnywhere Bash console and use the actual directory where you cloned the repository:

```bash
cd /home/kingsley2026/naija_fuel_finder
git pull origin main
```

Activate the virtualenv selected on the PythonAnywhere **Web** tab and install the pinned dependencies:

```bash
source /home/kingsley2026/.virtualenvs/<your-virtualenv-name>/bin/activate
pip install -r requirements.txt
```

### 3. Configure the WSGI file

On the **Web** tab, open the WSGI configuration file. Before the line that calls `get_wsgi_application()`, configure the project and production settings. Replace the placeholder secret with a newly generated, private value; never commit it or share it in chat.

```python
import os
import sys

project = "/home/kingsley2026/naija_fuel_finder"
if project not in sys.path:
    sys.path.insert(0, project)

os.environ["DJANGO_SETTINGS_MODULE"] = "config.settings"
os.environ["DJANGO_DEBUG"] = "false"
os.environ["DJANGO_SECRET_KEY"] = "<new-long-random-secret>"
os.environ["DJANGO_ALLOWED_HOSTS"] = "kingsley2026.pythonanywhere.com"
os.environ["CSRF_TRUSTED_ORIGINS"] = "https://kingsley2026.pythonanywhere.com"
os.environ["USE_X_FORWARDED_PROTO"] = "true"
```

Keep the WSGI file and its secret outside the Git repository. The app uses SQLite unless PostgreSQL environment variables are configured. Back up any existing database before changing database configuration.

### 4. Migrate data and collect static files

Run these commands from the project directory with the web app's virtualenv active:

```bash
python manage.py check
python manage.py migrate
python import_osm_json.py
python manage.py collectstatic --noinput
```

The station importer skips locations already in the database. In the **Web** tab, add a static-files mapping with URL `/static/` and directory `/home/kingsley2026/naija_fuel_finder/staticfiles`. Confirm the project path matches your actual clone directory.

### 5. Reload and verify

Click **Reload** in the PythonAnywhere **Web** tab, then visit `https://kingsley2026.pythonanywhere.com/` and check for the updated “Closest 10 in Nigeria” search option. If the site shows an error, inspect the error log linked from the Web tab.