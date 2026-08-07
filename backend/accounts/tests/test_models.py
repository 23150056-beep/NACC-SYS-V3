from django.test import TestCase
from django.contrib.auth import get_user_model
from accounts.models import Role

User = get_user_model()


class UserModelTest(TestCase):
    def test_create_user_with_role_and_fullname(self):
        role = Role.objects.create(role_name=Role.PSYCHOLOGIST)
        user = User.objects.create_user(
            email="jane@racco1.gov.ph",
            username="jane",
            password="secret123",
            first_name="Jane",
            last_name="Cruz",
            middle_initial="D",
            role=role,
        )
        self.assertTrue(user.check_password("secret123"))
        self.assertEqual(user.fullname, "Jane D Cruz")
        self.assertEqual(user.status, User.ACTIVE)
        self.assertEqual(user.role.role_name, "Psychologist")
