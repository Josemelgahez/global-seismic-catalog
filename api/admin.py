from django.contrib import admin
from .models import Earthquake, DuplicateLink, IntensityCurve, SyncState, CycleLog

admin.site.register(Earthquake)
admin.site.register(IntensityCurve)
admin.site.register(DuplicateLink)
admin.site.register(SyncState)
admin.site.register(CycleLog)