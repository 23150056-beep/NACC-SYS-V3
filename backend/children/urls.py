from rest_framework.routers import DefaultRouter
from children.views import GuardianViewSet, ChildViewSet

router = DefaultRouter()
router.register("guardians", GuardianViewSet, basename="guardian")
router.register("children", ChildViewSet, basename="child")

urlpatterns = router.urls
