from django.contrib import admin
from django.urls import path, include
from django.views.generic import RedirectView
from django.http import HttpResponseRedirect

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", RedirectView.as_view(url="/api/", permanent=True)),
    path("", include("api.urls")),
]

def redirect_to_api(request, exception=None):
    return HttpResponseRedirect("/api/")

handler404 = redirect_to_api
