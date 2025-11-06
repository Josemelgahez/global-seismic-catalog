from rest_framework import viewsets, filters
from rest_framework_gis.filters import InBBoxFilter
from django_filters.rest_framework import DjangoFilterBackend
import django_filters

from .models import Earthquake
from .serializers import EarthquakeSerializer

class EarthquakeFilter(django_filters.FilterSet):
    source = django_filters.ChoiceFilter(
        label="Source",
        choices=lambda: [(s, s) for s in Earthquake.objects.values_list("source", flat=True).distinct()],
    )

    origin_country = django_filters.CharFilter(
        field_name="origin_country",
        lookup_expr="iexact",
        label="Origin Country",
    )

    tectonic_plate = django_filters.CharFilter(
        field_name="tectonic_plate",
        lookup_expr="iexact",
        label="Tectonic Plate",
    )

    tsunami = django_filters.BooleanFilter(
        field_name="tsunami", label="Tsunami"
    )

    class Meta:
        model = Earthquake
        fields = ["source", "origin_country", "tectonic_plate", "tsunami"]

class EarthquakeViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Earthquake.objects.all().order_by("-origin_time")
    serializer_class = EarthquakeSerializer

    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
        InBBoxFilter,
    ]

    filterset_class = EarthquakeFilter
    search_fields = ["place_name", "source_id", "origin_country", "tectonic_plate"]
    ordering_fields = ["origin_time", "retrieved_time", "magnitude", "depth_km"]
    bbox_filter_field = "location"
    bbox_filter_include_overlapping = True
