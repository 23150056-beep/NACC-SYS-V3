"""List endpoints must not cost one query per row.

Every serializer in the clinical family renders a name off a related row —
`child.fullname`, `author.fullname` — so a queryset that forgets to join them
degrades into one extra query per record. It degrades quietly: the response is
byte-identical and every other test still passes. The only thing that changes
is the bill, and only in production, where each of those queries is a network
round-trip to another region rather than a local SQLite read.

Measured before the join was added: /api/remarks/ ran 306 queries to return
303 rows, /api/problems/ 81, /api/children/ 47 for 40 children. The ceilings
below are deliberately loose — this is a guard against the shape of the
regression (linear in rows), not a pin on an exact number, so ordinary changes
to authentication or filtering do not have to come here and edit it.
"""
from django.contrib.auth import get_user_model
from django.db import connection
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APITestCase

from accounts.models import Role
from children.models import Child
from clinical.models import ProblemEntry, RemarkNote, TreatmentPlan

User = get_user_model()

# Enough rows that a per-row query is unmistakable: at N=12 an unjoined list
# costs 13+ queries and a joined one costs ~3, so the ceiling cannot be met by
# accident.
ROWS = 12
CEILING = 8


class ListEndpointsDoNotScaleWithRowsTest(APITestCase):
    def setUp(self):
        self.admin_role = Role.objects.create(role_name=Role.ADMINISTRATOR)
        self.psy_role = Role.objects.create(role_name=Role.PSYCHOLOGIST)
        self.admin = User.objects.create_user(
            email="a@racco1.gov.ph", username="a", password="pass1234",
            role=self.admin_role)
        # Authors differ per row on purpose. A single shared author would be
        # served from Django's per-queryset cache and hide the very thing this
        # file exists to catch.
        self.psychologists = [
            User.objects.create_user(
                email=f"p{i}@racco1.gov.ph", username=f"p{i}",
                password="pass1234", role=self.psy_role)
            for i in range(ROWS)
        ]
        self.children = [
            Child.objects.create(fullname=f"Child {i}", case_type="Adoption",
                                 assigned_psychologist=self.psychologists[i])
            for i in range(ROWS)
        ]
        for i, child in enumerate(self.children):
            author = self.psychologists[i]
            RemarkNote.objects.create(child=child, author=author,
                                      date="2026-01-05", text=f"note {i}")
            TreatmentPlan.objects.create(child=child, author=author,
                                         objectives=f"plan {i}")
            ProblemEntry.objects.create(child=child, logged_by=author,
                                        description=f"problem {i}")

        token = self.client.post("/api/auth/login/", {
            "email": "a@racco1.gov.ph", "password": "pass1234"}).data["access"]
        self.client.credentials(HTTP_AUTHORIZATION="Bearer " + token)

    def _assert_flat(self, url):
        # A ceiling, not assertNumQueries, which pins an exact number and would
        # turn every unrelated query change into a failure here.
        with CaptureQueriesContext(connection) as queries:
            resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(len(resp.data), ROWS, f"{url} returned the wrong rows")
        self.assertLessEqual(
            len(queries), CEILING,
            f"{url} ran {len(queries)} queries for {ROWS} rows (ceiling "
            f"{CEILING}). That is one query per row again: check that the "
            f"viewset's select_related still covers every related field the "
            f"serializer renders.")

    def test_remarks_do_not_query_per_row(self):
        self._assert_flat("/api/remarks/")

    def test_treatment_plans_do_not_query_per_row(self):
        self._assert_flat("/api/treatment-plans/")

    def test_problems_do_not_query_per_row(self):
        self._assert_flat("/api/problems/")

    def test_the_child_list_does_not_query_per_row(self):
        """Same failure, different relation: the child list renders
        psychologist_name on every row."""
        self._assert_flat("/api/children/")
