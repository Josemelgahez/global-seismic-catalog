from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import EarthquakeViewSet

router = DefaultRouter()
router.register(r"earthquakes", EarthquakeViewSet)

urlpatterns = [
    path("api/", include(router.urls)),
]