import os
import django
import json

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from stations.models import Station

def import_geojson():
    file_path = os.path.join(os.path.dirname(__file__), 'data.json')
    
    if not os.path.exists(file_path):
        print("❌ Error: data.json not found in your folder.")
        return

    print("📂 Reading GeoJSON data... (This might take a minute)")
    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    created_count = 0
    skipped_count = 0

    print("⚙️ Processing stations...")

    for feature in data.get('features', []):
        props = feature.get('properties', {})
        
        # Double-check it's actually a fuel station
        if props.get('amenity') != 'fuel':
            continue

        # Extract and clean data
        name = props.get('name') or props.get('operator') or f"Fuel Station {props.get('@id', 'Unknown')}"
        brand = props.get('brand') or props.get('operator') or 'Independent'
        state = props.get('addr:state') or props.get('addr:city') or 'Unknown'
        
        name = str(name)[:255]
        brand = str(brand)[:50]
        state = str(state)[:50]

        # Extract coordinates from GeoJSON geometry
        # Note: GeoJSON always stores coordinates as [Longitude, Latitude]
        geom = feature.get('geometry', {})
        geom_type = geom.get('type')
        coords = geom.get('coordinates')
        
        lat = None
        lon = None

        if geom_type == 'Point':
            lon, lat = coords
        elif geom_type == 'Polygon':
            # Take the first coordinate of the outer ring
            lon, lat = coords[0][0]
        elif geom_type == 'MultiPolygon':
            # Take the first coordinate of the first polygon's outer ring
            lon, lat = coords[0][0][0]

        if lat and lon:
            # Check if it already exists to avoid duplicates
            if not Station.objects.filter(latitude=lat, longitude=lon).exists():
                Station.objects.create(
                    name=name,
                    brand=brand,
                    latitude=lat,
                    longitude=lon,
                    state=state
                )
                created_count += 1
            else:
                skipped_count += 1

    print(f"✅ Done! Added {created_count} new stations.")
    print(f"⏭️ Skipped {skipped_count} stations (already in database).")
    print("🚀 Open http://localhost:8000 and click 'Find Near Me' to see your massive map!")

if __name__ == '__main__':
    import_geojson()