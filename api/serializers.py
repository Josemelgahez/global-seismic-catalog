from rest_framework_gis.serializers import GeoFeatureModelSerializer
from rest_framework import serializers
from .models import Earthquake, CycleLog

class EarthquakeSerializer(GeoFeatureModelSerializer):
    class Meta:
        model = Earthquake
        geo_field = "location"
        fields = "__all__"

class CycleLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = CycleLog
        fields = "__all__"