from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include("accounts.urls")),
    path("api/", include("children.urls")),
    path("api/", include("activity.urls")),
    path("api/", include("clinical.urls")),
    path("api/", include("scheduling.urls")),
    path("api/", include("ai.urls")),
    path("api/", include("samd.urls")),
]
