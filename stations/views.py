import json
import math
from datetime import timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path

from django.conf import settings
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST
from django.db.models import Prefetch

from .models import PriceReport, Station


def index(request):
    """Render the station finder."""
    return render(request, "stations/index.html")


def _haversine(lat1, lon1, lat2, lon2):
    """Return the distance in kilometres between two coordinates."""
    earth_radius_km = 6371
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(dlon / 2) ** 2
    )
    return earth_radius_km * 2 * math.asin(math.sqrt(min(1, a)))


@require_GET
def api_nearby_stations(request):
    """Return nearby stations or the ten closest stations across the dataset."""
    try:
        lat = float(request.GET["lat"])
        lng = float(request.GET["lng"])
    except (KeyError, TypeError, ValueError):
        return JsonResponse(
            {"error": "Valid lat and lng coordinates are required."}, status=400
        )

    radius = request.GET.get("radius", "50")
    nationwide_search = radius == "nearest"
    if not nationwide_search:
        try:
            radius_km = int(radius)
        except (TypeError, ValueError):
            return JsonResponse(
                {"error": "Radius must be a distance in kilometres or 'nearest'."},
                status=400,
            )

    if (
        not math.isfinite(lat)
        or not math.isfinite(lng)
        or not -90 <= lat <= 90
        or not -180 <= lng <= 180
    ):
        return JsonResponse({"error": "Coordinates are out of range."}, status=400)
    if not nationwide_search and not 1 <= radius_km <= 100:
        return JsonResponse({"error": "Radius must be between 1 and 100 km."}, status=400)

    fuel_type = request.GET.get("fuel_type", "")
    valid_fuel_types = {choice[0] for choice in PriceReport.FUEL_TYPES}
    if fuel_type and fuel_type not in valid_fuel_types:
        return JsonResponse({"error": "Invalid fuel type."}, status=400)

    brand = request.GET.get("brand", "")
    valid_brands = {choice[0] for choice in Station.BRAND_CHOICES}
    if brand and brand not in valid_brands:
        return JsonResponse({"error": "Invalid station brand."}, status=400)

    reports = PriceReport.objects.all()
    if fuel_type:
        reports = reports.filter(fuel_type=fuel_type)
    reports = reports.order_by("-reported_at")[:1]

    stations = Station.objects.prefetch_related(
        Prefetch("reports", queryset=reports, to_attr="matching_reports")
    )
    if brand:
        stations = stations.filter(brand=brand)

    results = []
    for station in stations:
        distance = _haversine(
            lat, lng, float(station.latitude), float(station.longitude)
        )
        if not nationwide_search and distance > radius_km:
            continue

        latest_report = (
            station.matching_reports[0] if station.matching_reports else None
        )
        results.append(
            {
                "id": station.id,
                "name": station.name,
                "brand": station.brand,
                "lat": str(station.latitude),
                "lng": str(station.longitude),
                "distance_km": round(distance, 2),
                "price": str(latest_report.price_per_liter) if latest_report else None,
                "fuel_type": latest_report.fuel_type if latest_report else None,
                "queue": latest_report.queue_status if latest_report else None,
                "available": latest_report.is_available if latest_report else None,
                "updated": (
                    latest_report.reported_at.strftime("%Y-%m-%d %H:%M")
                    if latest_report
                    else None
                ),
            }
        )

    results.sort(key=lambda station: station["distance_km"])
    if nationwide_search:
        results = results[:10]
    return JsonResponse(results, safe=False)


@require_POST
def submit_report(request):
    if not request.user.is_authenticated:
        return JsonResponse({"error": "Please log in to report a price."}, status=401)

    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse({"error": "Request body must be valid JSON."}, status=400)
    if not isinstance(data, dict):
        return JsonResponse({"error": "Request body must be a JSON object."}, status=400)

    try:
        station_id = int(data["station_id"])
        price = Decimal(str(data["price"]))
    except (KeyError, TypeError, ValueError, InvalidOperation):
        return JsonResponse(
            {"error": "A valid station ID and price are required."}, status=400
        )

    station = Station.objects.filter(pk=station_id).first()
    if station is None:
        return JsonResponse({"error": "Station not found."}, status=404)

    fuel_type = data.get("fuel_type")
    valid_fuel_types = {choice[0] for choice in PriceReport.FUEL_TYPES}
    if fuel_type not in valid_fuel_types:
        return JsonResponse({"error": "Invalid fuel type."}, status=400)

    queue_status = data.get("queue_status", "NONE")
    valid_queue_statuses = {choice[0] for choice in PriceReport.QUEUE_STATUS}
    if queue_status not in valid_queue_statuses:
        return JsonResponse({"error": "Invalid queue status."}, status=400)

    if (
        not price.is_finite()
        or not Decimal("200") <= price <= Decimal("2000")
        or price.as_tuple().exponent < -2
    ):
        return JsonResponse(
            {
                "error": (
                    "Price must be between ₦200 and ₦2,000 per litre "
                    "and use no more than two decimal places."
                )
            },
            status=400,
        )

    is_available = data.get("is_available", True)
    if not isinstance(is_available, bool):
        return JsonResponse({"error": "Availability must be true or false."}, status=400)

    is_verified_owner = station.owner_id == request.user.id and station.is_verified
    one_day_ago = timezone.now() - timedelta(days=1)
    if not is_verified_owner and PriceReport.objects.filter(
        reporter=request.user,
        station=station,
        fuel_type=fuel_type,
        reported_at__gte=one_day_ago,
    ).exists():
        return JsonResponse(
            {
                "error": (
                    "You have already reported this station recently. "
                    "Please wait 24 hours."
                )
            },
            status=400,
        )

    user_ip = request.META.get("REMOTE_ADDR")
    one_hour_ago = timezone.now() - timedelta(hours=1)
    recent_ip_reports = PriceReport.objects.filter(
        reporter_ip=user_ip, reported_at__gte=one_hour_ago
    ).count()
    if recent_ip_reports >= 5:
        return JsonResponse(
            {
                "error": (
                    "Too many reports from your network recently. "
                    "Please wait an hour before submitting more."
                )
            },
            status=429,
        )

    PriceReport.objects.create(
        station=station,
        fuel_type=fuel_type,
        price_per_liter=price,
        queue_status=queue_status,
        is_available=is_available,
        reporter=request.user,
        reporter_ip=user_ip,
    )
    return JsonResponse(
        {"success": True, "message": "Report submitted successfully!"}
    )


def service_worker(request):
    sw_path = Path(settings.BASE_DIR) / "stations" / "static" / "sw.js"
    return HttpResponse(
        sw_path.read_text(encoding="utf-8"), content_type="application/javascript"
    )
