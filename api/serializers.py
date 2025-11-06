from rest_framework_gis.serializers import GeoFeatureModelSerializer
from rest_framework import serializers
from .models import Earthquake

class EarthquakeSerializer(GeoFeatureModelSerializer):
    class Meta:
        model = Earthquake
        geo_field = "location"
        fields = "__all__"
