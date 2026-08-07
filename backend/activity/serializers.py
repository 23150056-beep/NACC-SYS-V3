from rest_framework import serializers
from activity.models import ActivityLog


class ActivityLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = ActivityLog
        fields = [
            "id", "actor_label", "action", "category",
            "entity_type", "entity_label", "entity_id", "created_at",
        ]
