from django.contrib import admin
from .models import Earthquake, DuplicateLink, IntensityCurve, Country, Plate, SyncState

admin.site.register(Earthquake)
admin.site.register(IntensityCurve)
admin.site.register(DuplicateLink)
admin.site.register(Country)
admin.site.register(Plate)
admin.site.register(SyncState)