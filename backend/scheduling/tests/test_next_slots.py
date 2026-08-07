import datetime
from django.utils import timezone
from rest_framework.test import APITestCase
from accounts.models import Role
from children.tests.test_child_collab import make_user
from children.models import Child
from scheduling.models import AvailabilityBlock, Appointment


class NextSlotsTests(APITestCase):
    def setUp(self):
        self.staff = make_user("sl@t.ph", Role.STAFF)
        self.psych = make_user("pl@t.ph", Role.PSYCHOLOGIST)
        self.child = Child.objects.create(fullname="Slot Kid", assigned_psychologist=self.psych)
        self.tomorrow = timezone.localdate() + datetime.timedelta(days=1)
        self.block = AvailabilityBlock.objects.create(
            psychologist=self.psych, weekday=self.tomorrow.weekday(),
            start_time=datetime.time(9), end_time=datetime.time(12), capacity=2)
        self.client.force_authenticate(self.staff)

    def test_returns_upcoming_slots(self):
        r = self.client.get(f"/api/availability/next-slots/?child={self.child.id}")
        self.assertEqual(r.status_code, 200)
        self.assertGreaterEqual(len(r.data["slots"]), 1)
        self.assertEqual(r.data["slots"][0]["remaining"], 2)

    def test_unassigned_child_400(self):
        solo = Child.objects.create(fullname="No Psych")
        r = self.client.get(f"/api/availability/next-slots/?child={solo.id}")
        self.assertEqual(r.status_code, 400)

    def test_response_includes_psychologist_name(self):
        r = self.client.get(f"/api/availability/next-slots/?child={self.child.id}")
        self.assertEqual(r.data["psychologist"], self.psych.fullname or self.psych.email)

    def test_unknown_child_400(self):
        r = self.client.get("/api/availability/next-slots/?child=999999")
        self.assertEqual(r.status_code, 400)

    def test_unassigned_psychologist_gets_404(self):
        # A psychologist who isn't assigned to this child must not be able
        # to learn another psychologist's assigned-child name or their
        # availability windows via this endpoint.
        other_psych = make_user("op@t.ph", Role.PSYCHOLOGIST)
        self.client.force_authenticate(other_psych)
        r = self.client.get(f"/api/availability/next-slots/?child={self.child.id}")
        self.assertEqual(r.status_code, 404)

    def test_assigned_psychologist_can_query_own_child(self):
        self.client.force_authenticate(self.psych)
        r = self.client.get(f"/api/availability/next-slots/?child={self.child.id}")
        self.assertEqual(r.status_code, 200)

    def test_cancelled_appointment_does_not_reduce_remaining(self):
        # Mirrors _validate_booking: only CANCELLED is excluded from the count.
        start = timezone.make_aware(datetime.datetime.combine(self.tomorrow, datetime.time(9)))
        Appointment.objects.create(
            child=self.child, psychologist=self.psych, start=start,
            status=Appointment.CANCELLED)
        r = self.client.get(f"/api/availability/next-slots/?child={self.child.id}")
        first = next(s for s in r.data["slots"] if s["date"] == self.tomorrow.isoformat())
        self.assertEqual(first["remaining"], 2)

    def test_completed_appointment_reduces_remaining(self):
        # Mirrors _validate_booking: non-cancelled statuses (including completed
        # and no_show) still occupy capacity.
        start = timezone.make_aware(datetime.datetime.combine(self.tomorrow, datetime.time(9)))
        Appointment.objects.create(
            child=self.child, psychologist=self.psych, start=start,
            status=Appointment.COMPLETED)
        r = self.client.get(f"/api/availability/next-slots/?child={self.child.id}")
        first = next(s for s in r.data["slots"] if s["date"] == self.tomorrow.isoformat())
        self.assertEqual(first["remaining"], 1)

    def test_fully_booked_day_excluded_but_next_occurrence_shown(self):
        start = timezone.make_aware(datetime.datetime.combine(self.tomorrow, datetime.time(9)))
        Appointment.objects.create(child=self.child, psychologist=self.psych, start=start)
        Appointment.objects.create(
            child=self.child, psychologist=self.psych, start=start.replace(hour=10))
        r = self.client.get(f"/api/availability/next-slots/?child={self.child.id}")
        dates = [s["date"] for s in r.data["slots"]]
        self.assertNotIn(self.tomorrow.isoformat(), dates)
        next_week = (self.tomorrow + datetime.timedelta(days=7)).isoformat()
        self.assertIn(next_week, dates)
