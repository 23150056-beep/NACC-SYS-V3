from django.test import TestCase
from children.models import Guardian, Child


class ChildModelTest(TestCase):
    def test_child_links_to_guardian(self):
        g = Guardian.objects.create(fullname="Maria Cruz", gender="Female",
                                    address="Bauang", case_type="Foster")
        c = Child.objects.create(fullname="Juan Cruz", gender="Male",
                                 address="Bauang", case_type="Foster", guardian=g)
        self.assertEqual(c.guardian.fullname, "Maria Cruz")
        self.assertEqual(c.status, Child.ACTIVE)
