from django.db import models
from django.contrib.gis.db import models as gis_models
from django.contrib.gis.geos import Point

class Earthquake(models.Model):
    id = models.AutoField(primary_key=True, help_text="Internal database identifier")

    global_id = models.CharField(max_length=255, unique=True, db_index=True, help_text="Persistent global identifier generated from source and original identifier")
    
    source_id = models.CharField(max_length=255, blank=True, help_text="Original event identifier provided by the source catalog")
    source = models.CharField(max_length=255, blank=True, help_text="Original data provider that published this event record (e.g., USGS, IGN, EMSC)")

    origin_time = models.DateTimeField(help_text="Event origin time in UTC (ISO 8601 format)")
    latitude = models.FloatField(help_text="Epicentral latitude in decimal degrees")
    longitude = models.FloatField(help_text="Epicentral longitude in decimal degrees")
    location = gis_models.PointField(geography=True, null=True, blank=True, help_text="Epicentral point (longitude, latitude)")
    magnitude = models.FloatField(null=True, help_text="Reported event magnitude value")
    mag_type = models.CharField(max_length=16, null=True, blank=True, help_text="Type of magnitude reported (e.g., Mw, ML, Mb)")
    depth_km = models.FloatField(null=True, blank=True, help_text="Focal depth of the event in kilometers")

    place_name = models.CharField(max_length=255, null=True, blank=True, help_text="Nearest known place or region as reported by the source")
    origin_country = models.CharField(max_length=255, null=True, blank=True, help_text="Country determined from epicentral coordinates")
    tectonic_plate = models.CharField(max_length=255, null=True, blank=True, help_text="Name of the tectonic plate where the event occurred")
    affected_countries = models.JSONField(null=True, default=list, blank=True, help_text="List of countries potentially affected by the event or its intensity contours")

    tsunami = models.BooleanField(null=True, default=False, help_text="Indicates whether a tsunami was reported or associated with the event")
    has_curves = models.BooleanField(null=True, default=False, help_text="True if the event has associated intensity (shakemap) curves")

    updated_time = models.DateTimeField(null=True, blank=True, help_text="Timestamp of the last update received from the source feed (UTC)")
    retrieved_time = models.DateTimeField(null=True, blank=True, help_text="Timestamp when the event was retrieved by the local acquisition system (UTC)")

    raw_data = models.JSONField(null=True, blank=True, default=dict, help_text="Original raw JSON record from the source feed for reproducibility and provenance tracking")

    duplicate_of = models.ForeignKey(
        "self", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="duplicates",
        help_text="Reference to the canonical event if this record is classified as a duplicate of another"
    )

    class Meta:
        verbose_name = "Earthquake"
        verbose_name_plural = "Earthquakes"
        constraints = [
            models.UniqueConstraint(fields=["global_id"], name="unique_global_identifier")
        ]
        indexes = [
            models.Index(fields=["origin_time"]),
            models.Index(fields=["retrieved_time"]),
            models.Index(fields=["source"]),
        ]

    def save(self, *args, **kwargs):
        if self.latitude is not None and self.longitude is not None:
            try:
                self.location = Point(float(self.longitude), float(self.latitude))
            except Exception:
                self.location = None
        super().save(*args, **kwargs)

    def __str__(self):
        date_str = self.origin_time.strftime('%Y-%m-%d %H:%M:%S UTC') if self.origin_time else "Unknown time"
        loc_str = f"{self.place_name}" if self.place_name else f"{self.latitude:.2f}°, {self.longitude:.2f}°"
        return f"{self.source_id} | {date_str} | M{self.magnitude or '–'} ({self.mag_type or '–'}) | {loc_str}"

class DuplicateLink(models.Model):
    canonical = models.ForeignKey(Earthquake, on_delete=models.CASCADE, related_name="canonical_links", help_text="Reference to the canonical event representing this duplicate cluster")
    duplicate = models.ForeignKey(Earthquake, on_delete=models.CASCADE, related_name="duplicate_links", help_text="Reference to the secondary event considered a duplicate of the canonical one")
    
    dt = models.FloatField(help_text="Difference in origin time between canonical and duplicate events (seconds)")
    dd = models.FloatField(help_text="Epicentral distance between canonical and duplicate events (kilometers)")
    dm = models.FloatField(help_text="Magnitude difference between canonical and duplicate events")

    class Meta:
        verbose_name = "Duplicate link"
        verbose_name_plural = "Duplicate links"

    def __str__(self):
        dt = f"{self.dt:.1f}s" if self.dt is not None else "–"
        dd = f"{self.dd:.1f}km" if self.dd is not None else "–"
        dm = f"{self.dm:.2f}" if self.dm is not None else "–"
        return f"{self.canonical.source_id} ⇄ {self.duplicate.source_id} (Δt={dt}, Δd={dd}, ΔM={dm})"

class IntensityCurve(models.Model):
    earthquake = models.ForeignKey(Earthquake, on_delete=models.CASCADE, related_name="intensity_curves", help_text="Reference to the parent earthquake event")
    intensity = models.FloatField(help_text="Intensity level (MMI value) represented by this contour")
    coordinates = models.JSONField(help_text="List of polygon coordinates defining the contour geometry in GeoJSON format")

    def __str__(self):
        return f"{self.earthquake.source_id} – MMI {self.intensity:.1f}"

class Country(gis_models.Model):
    ogc_fid = gis_models.AutoField(primary_key=True)
    admin = gis_models.CharField(max_length=36, null=True, blank=True)
    sovereignt = gis_models.CharField(max_length=32, null=True, blank=True)
    geom = gis_models.MultiPolygonField(srid=4326)

    class Meta:
        managed = False
        db_table = "countries"

    def __str__(self):
        return self.admin or self.sovereignt or f"Country {self.ogc_fid}"

class Plate(gis_models.Model):
    ogc_fid = gis_models.AutoField(primary_key=True)
    platename = gis_models.CharField(max_length=255, null=True, blank=True)
    code = gis_models.CharField(max_length=16, null=True, blank=True)
    geom = gis_models.MultiPolygonField(srid=4326)

    class Meta:
        managed = False
        db_table = "plates"

    def __str__(self):
        return self.platename or self.code or f"Plate {self.ogc_fid}"

class SyncState(models.Model):
    key = models.CharField(max_length=50, unique=True)
    value = models.BooleanField(default=False)
    
    last_sync_start = models.DateTimeField(null=True, blank=True, help_text="UTC timestamp marking the beginning of the last synchronization window")
    last_sync_end = models.DateTimeField(null=True, blank=True, help_text="UTC timestamp marking the end of the last synchronization window")
    last_run_at = models.DateTimeField(null=True, blank=True, help_text="UTC timestamp of the most recent synchronization process")

    class Meta:
        db_table = "sync_state"
        verbose_name = "Synchronization state"
        verbose_name_plural = "Synchronization states"
        indexes = [models.Index(fields=["last_run_at"])]

    def __str__(self):
        status = "done" if self.value else "pending"
        run_time = self.last_run_at.strftime('%Y-%m-%d %H:%M:%S') if self.last_run_at else "never"
        return f"{self.key}: {status} (last run: {run_time})"