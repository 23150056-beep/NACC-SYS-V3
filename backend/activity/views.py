from rest_framework import mixins, viewsets, permissions
from accounts.models import Role
from activity.models import ActivityLog
from activity.serializers import ActivityLogSerializer
from accounts.scoping import role_of


class ActivityLogViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = None
    serializer_class = ActivityLogSerializer

    def get_queryset(self):
        qs = ActivityLog.objects.all()
        role = role_of(self.request)
        if role == Role.PSYCHOLOGIST:
            # Psychologists only see notifications targeted at them.
            qs = qs.filter(recipient=self.request.user)
        elif role == Role.STAFF:
            # Staff see the case-coordination stream (records + assessments).
            # "Guardian" stays in this list although the model is gone: these
            # are log rows, and the ones written before July still say it.
            # Dropping it here would hide history, not tidy it.
            qs = qs.filter(category=ActivityLog.RECORD,
                           entity_type__in=["Child", "Guardian", "Assessment"])
        # Administrator: full audit stream (unchanged).
        category = self.request.query_params.get("category")
        if category:
            qs = qs.filter(category=category)
        return qs[:50]
