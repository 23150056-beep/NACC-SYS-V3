from django.urls import path, include
from rest_framework.routers import DefaultRouter

from samd.views import ChecklistView, SamdAssessmentViewSet

router = DefaultRouter()
router.register("samd/assessments", SamdAssessmentViewSet, basename="samd-assessment")

urlpatterns = [
    path("samd/checklist/", ChecklistView.as_view(), name="samd-checklist"),
    path("", include(router.urls)),
]
