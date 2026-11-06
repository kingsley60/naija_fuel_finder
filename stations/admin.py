from django.contrib import admin
from .models import Station, PriceReport

@admin.register(Station)
class StationAdmin(admin.ModelAdmin):
    list_display = ['name', 'brand', 'state', 'latitude', 'longitude']
    list_filter = ['brand', 'state']

@admin.register(PriceReport)
class PriceReportAdmin(admin.ModelAdmin):
    list_display = ['station', 'fuel_type', 'price_per_liter', 'queue_status', 'reported_at']