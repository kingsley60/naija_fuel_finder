from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('api/stations/', views.api_nearby_stations, name='api_stations'),
    path('api/report/', views.submit_report, name='submit_report'),
    path('sw.js', views.service_worker, name='service_worker'),
]