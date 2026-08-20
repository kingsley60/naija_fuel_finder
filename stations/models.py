from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.contrib.auth.models import User

class Station(models.Model):
    BRAND_CHOICES = [
        ('NNPC', 'NNPC'), ('TOTAL', 'Total Energies'),
        ('OANDO', 'Oando'), ('AP', 'AP'), ('INDEPENDENT', 'Independent')
    ]
    name = models.CharField(max_length=255)
    brand = models.CharField(max_length=50, choices=BRAND_CHOICES, blank=True)
    latitude = models.DecimalField(max_digits=9, decimal_places=6)
    longitude = models.DecimalField(max_digits=9, decimal_places=6)
    address = models.TextField(blank=True)
    state = models.CharField(max_length=50)
    created_at = models.DateTimeField(auto_now_add=True)
    owner = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='owned_stations')
    is_verified = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.name} ({self.state})"

    @property
    def latest_report(self):
        return self.reports.first()

class PriceReport(models.Model):
    FUEL_TYPES = [('PMS', 'Petrol'), ('AGO', 'Diesel'), ('LPG', 'Cooking Gas')]
    QUEUE_STATUS = [
        ('NONE', 'No Queue'), ('SHORT', 'Short (<30min)'),
        ('LONG', 'Long (30min-2hr)'), ('VERY_LONG', 'Very Long (>2hr)')
    ]
    station = models.ForeignKey(Station, on_delete=models.CASCADE, related_name='reports')
    fuel_type = models.CharField(max_length=10, choices=FUEL_TYPES)
    price_per_liter = models.DecimalField(
        max_digits=7, decimal_places=2,
        validators=[MinValueValidator(200), MaxValueValidator(2000)]
    )
    is_available = models.BooleanField(default=True)
    queue_status = models.CharField(max_length=20, choices=QUEUE_STATUS, default='NONE')
    reported_at = models.DateTimeField(auto_now_add=True)
    reporter_ip = models.GenericIPAddressField(null=True, blank=True)

    reporter = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        ordering = ['-reported_at']