import os
import django
import requests
import time

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from stations.models import Station

def import_osm_stations():
    print(" Fetching fuel stations from OpenStreetMap... (This may take 15-30 seconds)")
    
    # Overpass API query to get all fuel stations in Nigeria
    query = """
    [out:json][timeout:300];
    area["ISO3166-1"="NG"]->.searchArea;
    (
      node["amenity"="fuel"](area.searchArea);
    );
    out body;
    """
    
        # Use a highly reliable mirror server
    url = "https://overpass.kumi.systems/api/interpreter"
    
    # Add a User-Agent header so the server accepts our request
    headers = {
        'User-Agent': 'NaijaFuelFinder/1.0 (Educational Project)'
    }
    
    try:
        response = requests.get(url, params={'data': query}, headers=headers)
        response.raise_for_status()
        data = response.json()
        
        created_count = 0
        skipped_count = 0
        
        for element in data.get('elements', []):
            tags = element.get('tags', {})
            
            # Extract data
            name = tags.get('name') or tags.get('operator') or f"Fuel Station {element['id']}"
            brand = tags.get('brand') or tags.get('operator') or 'Independent'
            lat = element.get('lat')
            lon = element.get('lon')
            state = tags.get('addr:state') or tags.get('addr:city') or 'Unknown'
            
            # Clean up data to fit our database limits
            name = str(name)[:255]
            brand = str(brand)[:50]
            state = str(state)[:50]
            
            if lat and lon:
                # Prevent duplicate coordinates
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
                    
        print(f"✅ Success! Added {created_count} new stations.")
        print(f"⏭️ Skipped {skipped_count} stations (already in database).")
        
    except requests.exceptions.RequestException as e:
        print(f" Error fetching data: {e}")

if __name__ == '__main__':
    import_osm_stations()