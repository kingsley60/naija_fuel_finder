import os
from django.conf import settings
from django.http import HttpResponse
import json
import math
from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
from .models import Station, PriceReport
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from datetime import timedelta


def index(request):
    """Renders the main HTML page"""
    return render(request, 'stations/index.html')

def _haversine(lat1, lon1, lat2, lon2):
    """Calculates the distance in KM between two coordinates"""
    R = 6371 # Earth radius in km
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon/2)**2
    c = 2 * math.asin(math.sqrt(a))
    return R * c

def api_nearby_stations(request):
    """Returns JSON list of stations near the user"""
    try:
        # Default to Abuja if no location is provided
        lat = float(request.GET.get('lat', 9.0765)) 
        lng = float(request.GET.get('lng', 7.3986))
        radius_km = int(request.GET.get('radius', 100)) 
        fuel_type = request.GET.get('fuel_type', '')
        brand = request.GET.get('brand', '')
    except ValueError:
        return JsonResponse({'error': 'Invalid coordinates'}, status=400)

    stations = Station.objects.all()
    results = []

    for s in stations:
        dist = _haversine(lat, lng, float(s.latitude), float(s.longitude))
        if dist > radius_km:
            continue # Skip stations outside the radius

        lr = s.latest_report
        if fuel_type and lr and lr.fuel_type != fuel_type:
            continue
        if brand and s.brand != brand:
            continue

        results.append({
            'id': s.id, 
            'name': s.name, 
            'brand': s.brand,
            'lat': str(s.latitude), 
            'lng': str(s.longitude),
            'distance_km': round(dist, 2),
            'price': str(lr.price_per_liter) if lr else None,
            'fuel_type': lr.fuel_type if lr else None,
            'queue': lr.queue_status if lr else None,
            'available': lr.is_available if lr else None,
            'updated': lr.reported_at.strftime('%Y-%m-%d %H:%M') if lr else None,
        })
        
    return JsonResponse(sorted(results, key=lambda x: x['distance_km']), safe=False)

@login_required
@csrf_exempt
@require_POST
def submit_report(request):
    try:
        data = json.loads(request.body)
        station_id = data['station_id']
        fuel_type = data['fuel_type']
        
                # --- SPAM PROTECTION LAYER 1: User Duplicate Check ---
        # Check if the user is the verified owner of this station
        is_owner = (station.owner == request.user)

        if not is_owner:
            # If they are NOT the owner, enforce the 24-hour limit
            one_day_ago = timezone.now() - timedelta(days=1)
            recent_user_report = PriceReport.objects.filter(
                reporter=request.user,
                station_id=station_id,
                fuel_type=fuel_type,
                reported_at__gte=one_day_ago
            ).exists()
            
            if recent_user_report:
                return JsonResponse({
                    'error': 'You have already reported this station recently. Please wait 24 hours.'
                }, status=400)
            
        # --- SPAM PROTECTION LAYER 2: IP Rate Limiting ---
        # Prevent a single device/network from submitting more than 5 reports in 1 hour
        user_ip = request.META.get('REMOTE_ADDR', '127.0.0.1')
        one_hour_ago = timezone.now() - timedelta(hours=1)
        recent_ip_reports = PriceReport.objects.filter(
            reporter_ip=user_ip,
            reported_at__gte=one_hour_ago
        ).count()
        
        if recent_ip_reports >= 5:
            return JsonResponse({
                'error': 'Too many reports from your network recently. Please wait an hour before submitting more.'
            }, status=429) # 429 = Too Many Requests

        # --- If all checks pass, save the report ---
        station = Station.objects.get(id=station_id)
        PriceReport.objects.create(
            station=station,
            fuel_type=fuel_type,
            price_per_liter=data['price'],
            queue_status=data.get('queue_status', 'NONE'),
            is_available=data.get('is_available', True),
            reporter=request.user,
            reporter_ip=user_ip
        )
        return JsonResponse({'success': True, 'message': 'Report submitted successfully!'})
        
    except Station.DoesNotExist:
        return JsonResponse({'error': 'Station not found.'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)

    def service_worker(request):
        # Read the sw.js file from the static folder and serve it at the root URL
        sw_path = os.path.join(settings.BASE_DIR, 'stations', 'static', 'sw.js')
        with open(sw_path, 'r', encoding='utf-8') as f:
            return HttpResponse(f.read(), content_type='application/javascript')
import os
from django.conf import settings
from django.http import HttpResponse

def service_worker(request):
    sw_path = os.path.join(settings.BASE_DIR, 'stations', 'static', 'sw.js')
    with open(sw_path, 'r', encoding='utf-8') as f:
        return HttpResponse(f.read(), content_type='application/javascript')
