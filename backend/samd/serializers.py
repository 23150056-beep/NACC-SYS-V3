from rest_framework import serializers

from samd.models import SamdAssessment, SamdResponse
from samd.scoring import compute_scores


class SamdResponseSerializer(serializers.ModelSerializer):
    class Meta:
        model = SamdResponse
        fields = ["item_key", "compliance", "remarks"]


class SamdAssessmentListSerializer(serializers.ModelSerializer):
    """Used for list/create. `label` is optional on create — a default is
    filled in by the view (SamdAssessmentViewSet.perform_create)."""
    label = serializers.CharField(required=False, allow_blank=True)
    summary = serializers.SerializerMethodField()

    class Meta:
        model = SamdAssessment
        fields = ["id", "label", "status", "created_at", "completed_at", "summary"]
        read_only_fields = ["status", "created_at", "completed_at"]

    def get_summary(self, obj):
        return compute_scores(obj)["overall"]


class SamdAssessmentLabelSerializer(serializers.ModelSerializer):
    """PATCH .../assessments/{id}/ only ever touches the label."""
    class Meta:
        model = SamdAssessment
        fields = ["id", "label"]


class SamdAssessmentDetailSerializer(serializers.ModelSerializer):
    responses = SamdResponseSerializer(many=True, read_only=True)
    scores = serializers.SerializerMethodField()

    class Meta:
        model = SamdAssessment
        fields = ["id", "label", "status", "created_at", "completed_at", "responses", "scores"]

    def get_scores(self, obj):
        return compute_scores(obj)
