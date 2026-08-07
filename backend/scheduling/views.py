from datetime import datetime, time, timedelta

from django.utils import timezone
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from accounts.models import Role
from activity.models import ActivityLog
from activity.services import log_activity
from children.models import Child
from scheduling.models import AvailabilityBlock, Appointment
from scheduling.serializers import AvailabilityBlockSerializer, AppointmentSerializer


def _role(request):
    return getattr(getattr(request.user, "role", None), "role_name", None)


class AvailabilityBlockViewSet(viewsets.ModelViewSet):
    """Psychologists manage their own availability; admin manages all;
    staff read (to book against)."""
    permission_classes = [IsAuthenticated]
    pagination_class = None
    serializer_class = AvailabilityBlockSerializer

    def get_queryset(self):
        qs = AvailabilityBlock.objects.select_related("psychologist")
        if self.request.query_params.get("include_inactive") != "true":
            qs = qs.filter(active=True)
        psy = self.request.query_params.get("psychologist")
        if psy and str(psy).isdigit():
            qs = qs.filter(psychologist_id=psy)
        return qs

    def _assert_can_write(self, psychologist_id):
        role = _role(self.request)
        if role == Role.ADMINISTRATOR:
            return
        if role == Role.PSYCHOLOGIST and psychologist_id == self.request.user.id:
            return
        raise PermissionDenied("You can only manage your own availability.")

    def perform_create(self, serializer):
        role = _role(self.request)
        if role == Role.PSYCHOLOGIST:
            serializer.save(psychologist=self.request.user)
        else:
            psy = serializer.validated_data.get("psychologist")
            if psy is None:
                raise ValidationError({"psychologist": "Select the psychologist."})
            self._assert_can_write(psy.id)
            serializer.save()

    def perform_update(self, serializer):
        self._assert_can_write(serializer.instance.psychologist_id)
        serializer.save()

    def perform_destroy(self, instance):
        self._assert_can_write(instance.psychologist_id)
        instance.delete()

    @action(detail=False, methods=["get"], url_path="next-slots")
    def next_slots(self, request):
        """Upcoming bookable windows for a child's assigned psychologist —
        staff/psychologist see at a glance when the child can be counseled.
        Capacity counting mirrors AppointmentViewSet._validate_booking: every
        non-cancelled appointment inside the block's time window occupies a
        slot, so this never contradicts what the booking endpoint accepts."""
        child_id = request.query_params.get("child")
        try:
            child = Child.objects.get(pk=child_id)
        except (Child.DoesNotExist, ValueError, TypeError):
            return Response({"detail": "Unknown child."}, status=400)
        # Admin/Staff may query any child, unrestricted. A psychologist may
        # only query a child assigned to them - matching ChildViewSet's
        # get_queryset() scoping. Access outside that scope 404s rather than
        # 403ing, the same "hidden, not disclosed" convention used elsewhere
        # for a psychologist's access to a child outside their assignment.
        if (_role(request) == Role.PSYCHOLOGIST
                and child.assigned_psychologist_id != request.user.id):
            return Response({"detail": "Not found."}, status=404)
        psych = child.assigned_psychologist
        if psych is None:
            return Response({"detail": "This child has no assigned psychologist yet."}, status=400)
        blocks = AvailabilityBlock.objects.filter(psychologist=psych, active=True)
        today = timezone.localdate()
        slots = []
        for offset in range(0, 14):
            day = today + timedelta(days=offset)
            day_start = timezone.make_aware(datetime.combine(day, time.min))
            for b in blocks:
                if b.date is not None and b.date != day:
                    continue
                if b.date is None and (b.weekday is None or b.weekday != day.weekday()):
                    continue
                taken = (Appointment.objects
                         .filter(psychologist=psych,
                                 start__gte=day_start, start__lt=day_start + timedelta(days=1))
                         .exclude(status=Appointment.CANCELLED)
                         .filter(start__time__gte=b.start_time, start__time__lt=b.end_time)
                         .count())
                remaining = b.capacity - taken
                if remaining > 0:
                    slots.append({
                        "date": day.isoformat(),
                        "weekday": day.strftime("%A"),
                        "start": str(b.start_time)[:5], "end": str(b.end_time)[:5],
                        "remaining": remaining,
                    })
            if len(slots) >= 6:
                break
        return Response({
            "psychologist": getattr(psych, "fullname", "") or psych.get_username(),
            "slots": slots[:6],
        })


class AppointmentViewSet(viewsets.ModelViewSet):
    """Calendar appointments. Staff/admin book against a psychologist's
    availability; a psychologist may book freely on their own schedule.
    Status transitions via actions (completed / no_show / cancelled)."""
    permission_classes = [IsAuthenticated]
    pagination_class = None
    serializer_class = AppointmentSerializer

    def get_queryset(self):
        qs = Appointment.objects.select_related("child", "psychologist", "booked_by")
        role = _role(self.request)
        if role == Role.PSYCHOLOGIST:
            qs = qs.filter(psychologist=self.request.user)
        frm = self.request.query_params.get("from")
        to = self.request.query_params.get("to")
        if frm:
            qs = qs.filter(start__date__gte=frm)
        if to:
            qs = qs.filter(start__date__lte=to)
        child = self.request.query_params.get("child")
        if child and str(child).isdigit():
            qs = qs.filter(child_id=child)
        return qs

    def _validate_booking(self, psychologist, start, duration_minutes):
        """Staff/admin bookings must land inside an active availability block
        with free capacity. Psychologists may override on their own calendar."""
        role = _role(self.request)
        if role == Role.PSYCHOLOGIST and psychologist.id == self.request.user.id:
            return
        local = timezone.localtime(start) if timezone.is_aware(start) else start
        blocks = [b for b in psychologist.availability_blocks.filter(active=True)
                  if b.covers(local)]
        if not blocks:
            raise ValidationError(
                {"start": "That time is outside the psychologist's availability."})
        block = blocks[0]
        day_start = local.replace(hour=0, minute=0, second=0, microsecond=0)
        taken = (Appointment.objects
                 .filter(psychologist=psychologist,
                         start__gte=day_start, start__lt=day_start + timedelta(days=1))
                 .exclude(status=Appointment.CANCELLED)
                 .filter(start__time__gte=block.start_time, start__time__lt=block.end_time)
                 .count())
        if taken >= block.capacity:
            raise ValidationError({"start": "That availability block is fully booked."})

    def perform_create(self, serializer):
        role = _role(self.request)
        if role == Role.PSYCHOLOGIST:
            psychologist = self.request.user
        else:
            psychologist = serializer.validated_data.get("psychologist")
            if psychologist is None:
                raise ValidationError({"psychologist": "Select the psychologist."})
        self._validate_booking(psychologist,
                               serializer.validated_data["start"],
                               serializer.validated_data.get("duration_minutes", 60))
        obj = serializer.save(psychologist=psychologist, booked_by=self.request.user)
        log_activity(self.request.user, ActivityLog.CREATED, ActivityLog.RECORD,
                     entity_type="Appointment", entity_label=obj.child.fullname,
                     entity_id=obj.id, recipient=obj.psychologist)

    def _set_status(self, request, pk, new_status):
        obj = self.get_object()
        role = _role(request)
        allowed = role == Role.ADMINISTRATOR or obj.psychologist_id == request.user.id \
            or (role == Role.STAFF and new_status == Appointment.CANCELLED)
        if not allowed:
            return Response({"detail": "You cannot update this appointment."},
                            status=status.HTTP_403_FORBIDDEN)
        obj.status = new_status
        obj.save(update_fields=["status", "updated_at"])
        log_activity(request.user, ActivityLog.UPDATED, ActivityLog.RECORD,
                     entity_type="Appointment", entity_label=obj.child.fullname,
                     entity_id=obj.id, recipient=obj.psychologist)
        return Response(AppointmentSerializer(obj).data)

    @action(detail=True, methods=["post"])
    def complete(self, request, pk=None):
        return self._set_status(request, pk, Appointment.COMPLETED)

    @action(detail=True, methods=["post"])
    def no_show(self, request, pk=None):
        return self._set_status(request, pk, Appointment.NO_SHOW)

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        return self._set_status(request, pk, Appointment.CANCELLED)
