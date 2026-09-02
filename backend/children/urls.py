from rest_framework.routers import DefaultRouter
from children.views import ChildViewSet

router = DefaultRouter()
router.register("children", ChildViewSet, basename="child")

urlpatterns = router.urls
