from rest_framework.routers import DefaultRouter

from locations.views import BarangayViewSet, MunicipalityViewSet, ProvinceViewSet

router = DefaultRouter()
router.register(r"provinces", ProvinceViewSet, basename="province")
router.register(r"municipalities", MunicipalityViewSet, basename="municipality")
router.register(r"barangays", BarangayViewSet, basename="barangay")

urlpatterns = router.urls
