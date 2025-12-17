from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import EarthquakeViewSet, CycleLogViewSet

router = DefaultRouter()
router.register(r"earthquakes", EarthquakeViewSet)
router.register(r"cycle-logs", CycleLogViewSet)

urlpatterns = [
    path("api/", include(router.urls)),
]