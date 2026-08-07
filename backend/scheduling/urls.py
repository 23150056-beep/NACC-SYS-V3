from rest_framework.routers import DefaultRouter
from scheduling.views import AvailabilityBlockViewSet, AppointmentViewSet

router = DefaultRouter()
router.register("availability", AvailabilityBlockViewSet, basename="availability")
router.register("appointments", AppointmentViewSet, basename="appointment")

urlpatterns = router.urls
