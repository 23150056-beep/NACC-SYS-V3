from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_page
from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated

from locations.models import Barangay, Municipality, Province
from locations.serializers import (
    BarangaySerializer, MunicipalitySerializer, ProvinceSerializer)

# Reference data that changes a few times a year, read on every intake. An hour
# of caching costs nothing and spares the database 3,000-row barangay reads.
_CACHE_SECONDS = 60 * 60


class _PlaceViewSet(viewsets.ReadOnlyModelViewSet):
    """Read-only by construction: PSGC is maintained by the PSA, and the only
    supported way to change it here is re-running the seed command against a
    newer release. No endpoint can write."""

    permission_classes = [IsAuthenticated]
    pagination_class = None
    lookup_field = "psgc_code"

    @method_decorator(cache_page(_CACHE_SECONDS))
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)


class ProvinceViewSet(_PlaceViewSet):
    queryset = Province.objects.all()
    serializer_class = ProvinceSerializer


class MunicipalityViewSet(_PlaceViewSet):
    serializer_class = MunicipalitySerializer

    def get_queryset(self):
        qs = Municipality.objects.all()
        province = self.request.query_params.get("province")
        # Unfiltered returns every LGU, which is 125 rows for Region I and
        # would be ~1,600 nationwide. Fine now; the filter is what the cascading
        # form actually uses.
        return qs.filter(province__psgc_code=province) if province else qs


class BarangayViewSet(_PlaceViewSet):
    serializer_class = BarangaySerializer

    def get_queryset(self):
        qs = Barangay.objects.all()
        municipality = self.request.query_params.get("municipality")
        if municipality:
            return qs.filter(municipality__psgc_code=municipality)
        # 3,265 rows unfiltered is not a list any human picks from, and it is
        # not what the form asks for. Require the parent.
        return qs.none()
