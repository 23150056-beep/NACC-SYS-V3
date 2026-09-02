from django.test import TestCase
from children.models import Child


class ChildModelTest(TestCase):
    def test_a_new_child_starts_active(self):
        """Half of what this file used to assert. The other half was the
        guardian link, which went with the model in 0018 — but the default
        status is still worth pinning here rather than only through the API,
        because everything downstream branches on it."""
        c = Child.objects.create(fullname="Juan Cruz", gender="Male",
                                 address="Bauang", case_type="Foster")
        self.assertEqual(c.status, Child.ACTIVE)
        self.assertEqual(c.fullname, "Juan Cruz")
