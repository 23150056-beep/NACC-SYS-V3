from django.utils import timezone
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import IsAdministrator
from activity.models import ActivityLog
from activity.services import log_activity
from samd.checklist import CHECKLIST, ITEM_INDEX
from samd.models import SamdAssessment, SamdResponse
from samd.scoring import BANDS, compute_scores
from samd.serializers import (
    SamdAssessmentDetailSerializer, SamdAssessmentLabelSerializer, SamdAssessmentListSerializer,
)

VALID_COMPLIANCE = {"", SamdResponse.YES, SamdResponse.NOT, SamdResponse.NA}


class ChecklistView(APIView):
    """Static checklist structure (3 KRAs, 83 indicators) plus the
    certification band definitions, for the frontend to render the form."""
    permission_classes = [IsAdministrator]

    def get(self, request):
        return Response({"kras": CHECKLIST, "bands": BANDS})


class SamdAssessmentViewSet(viewsets.ModelViewSet):
    """Admin-only: SAMD certification-readiness self-assessment rounds."""
    permission_classes = [IsAdministrator]
    pagination_class = None
    http_method_names = ["get", "post", "patch", "head", "options"]
    queryset = SamdAssessment.objects.all()

    def get_serializer_class(self):
        if self.action == "retrieve":
            return SamdAssessmentDetailSerializer
        if self.action == "partial_update":
            return SamdAssessmentLabelSerializer
        return SamdAssessmentListSerializer

    def perform_create(self, serializer):
        label = serializer.validated_data.get("label") or ""
        label = label.strip() or f"Self-assessment {timezone.localdate().isoformat()}"
        obj = serializer.save(created_by=self.request.user, label=label)
        log_activity(self.request.user, ActivityLog.CREATED, ActivityLog.RECORD,
                     entity_type="SamdAssessment", entity_label=obj.label, entity_id=obj.id)

    @action(detail=True, methods=["post"])
    def respond(self, request, pk=None):
        assessment = self.get_object()
        if assessment.status == SamdAssessment.COMPLETED:
            return Response({"detail": "This assessment is completed and locked."}, status=400)

        item_key = request.data.get("item_key")
        compliance = request.data.get("compliance", "")
        remarks = (request.data.get("remarks") or "").strip()

        if item_key not in ITEM_INDEX:
            return Response({"item_key": "Unknown checklist item."}, status=400)
        if compliance not in VALID_COMPLIANCE:
            return Response({"compliance": 'Must be one of "yes", "not", "na", or "".'}, status=400)

        if not compliance and not remarks:
            SamdResponse.objects.filter(assessment=assessment, item_key=item_key).delete()
        else:
            SamdResponse.objects.update_or_create(
                assessment=assessment, item_key=item_key,
                defaults={"compliance": compliance, "remarks": remarks},
            )
        return Response(compute_scores(assessment))

    @action(detail=True, methods=["post"])
    def complete(self, request, pk=None):
        assessment = self.get_object()
        if assessment.status == SamdAssessment.COMPLETED:
            return Response({"detail": "This assessment is already completed."}, status=400)
        assessment.status = SamdAssessment.COMPLETED
        assessment.completed_at = timezone.now()
        assessment.save(update_fields=["status", "completed_at"])
        log_activity(request.user, ActivityLog.UPDATED, ActivityLog.RECORD,
                     entity_type="SamdAssessment", entity_label=assessment.label, entity_id=assessment.id)
        return Response(SamdAssessmentDetailSerializer(assessment).data)
