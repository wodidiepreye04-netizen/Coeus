from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path("admin/", admin.site.urls),
    path("therapist/", include("core.urls_therapist")),
    path("", include("core.urls")),
]
