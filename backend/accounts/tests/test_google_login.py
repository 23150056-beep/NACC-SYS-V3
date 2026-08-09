"""Google Sign-In: who gets in, and — more importantly — who does not."""

from unittest import mock

from django.test import override_settings
from rest_framework.test import APITestCase

from accounts.models import Role, User
from children.tests.test_child_collab import make_user

GOOGLE_CLIENT_ID = "test-client-id.apps.googleusercontent.com"
VERIFY = "accounts.google_auth.id_token.verify_oauth2_token"


def claims(email, sub="google-sub-123", verified=True, **extra):
    payload = {
        "iss": "https://accounts.google.com",
        "aud": GOOGLE_CLIENT_ID,
        "sub": sub,
        "email": email,
        "email_verified": verified,
    }
    payload.update(extra)
    return payload


@override_settings(GOOGLE_OAUTH_CLIENT_ID=GOOGLE_CLIENT_ID, GOOGLE_ALLOWED_DOMAINS=[])
class GoogleLoginTests(APITestCase):
    def setUp(self):
        self.staff = make_user("staff@racco1.gov.ph", Role.STAFF)
        self.psych = make_user("psych@racco1.gov.ph", Role.PSYCHOLOGIST)
        self.admin = make_user("admin@racco1.gov.ph", Role.ADMINISTRATOR)

    def post(self, credential="tok"):
        return self.client.post("/api/auth/google/", {"credential": credential}, format="json")

    # --- accepted -------------------------------------------------------

    def test_staff_can_sign_in(self):
        with mock.patch(VERIFY, return_value=claims("staff@racco1.gov.ph")):
            r = self.post()
        self.assertEqual(r.status_code, 200, r.data)
        # Same envelope as a password login, so the frontend stores it identically.
        self.assertEqual(set(r.data), {"refresh", "access", "user"})
        self.assertEqual(r.data["user"]["email"], "staff@racco1.gov.ph")

    def test_psychologist_can_sign_in(self):
        with mock.patch(VERIFY, return_value=claims("psych@racco1.gov.ph")):
            self.assertEqual(self.post().status_code, 200)

    def test_issued_token_actually_works(self):
        with mock.patch(VERIFY, return_value=claims("staff@racco1.gov.ph")):
            token = self.post().data["access"]
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
        me = self.client.get("/api/auth/me/")
        self.assertEqual(me.status_code, 200)
        self.assertEqual(me.data["email"], "staff@racco1.gov.ph")

    def test_first_sign_in_links_the_google_subject(self):
        with mock.patch(VERIFY, return_value=claims("staff@racco1.gov.ph", sub="sub-abc")):
            self.post()
        self.staff.refresh_from_db()
        self.assertEqual(self.staff.google_sub, "sub-abc")

    def test_later_sign_in_matches_on_subject_not_email(self):
        # Google-side email change must not lock the user out of their account.
        self.staff.google_sub = "sub-abc"
        self.staff.save(update_fields=["google_sub"])
        with mock.patch(VERIFY, return_value=claims("new-address@gmail.com", sub="sub-abc")):
            r = self.post()
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["user"]["email"], "staff@racco1.gov.ph")

    def test_forced_password_change_is_cleared(self):
        # A Google user has no password to rotate; leaving the flag set would
        # trap them in the change-password gate forever.
        self.staff.must_change_password = True
        self.staff.save(update_fields=["must_change_password"])
        with mock.patch(VERIFY, return_value=claims("staff@racco1.gov.ph")):
            token = self.post().data["access"]
        self.staff.refresh_from_db()
        self.assertFalse(self.staff.must_change_password)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
        self.assertEqual(self.client.get("/api/children/").status_code, 200)

    # --- refused --------------------------------------------------------

    def test_administrator_is_refused(self):
        # Admins keep password login: tying the recovery account to a third
        # party means a Google outage locks the agency out of its own records.
        with mock.patch(VERIFY, return_value=claims("admin@racco1.gov.ph")):
            r = self.post()
        self.assertEqual(r.status_code, 401)
        self.assertIn("password", str(r.data).lower())

    def test_unknown_email_is_refused_and_creates_nothing(self):
        before = User.objects.count()
        with mock.patch(VERIFY, return_value=claims("stranger@gmail.com")):
            r = self.post()
        self.assertEqual(r.status_code, 401)
        self.assertEqual(User.objects.count(), before)
        self.assertFalse(User.objects.filter(email="stranger@gmail.com").exists())

    def test_archived_user_is_refused(self):
        self.staff.status = User.ARCHIVED
        self.staff.is_active = False
        self.staff.save(update_fields=["status", "is_active"])
        with mock.patch(VERIFY, return_value=claims("staff@racco1.gov.ph")):
            self.assertEqual(self.post().status_code, 401)

    def test_unverified_google_email_is_refused(self):
        # Otherwise anyone could claim a staff address on a throwaway account.
        with mock.patch(VERIFY, return_value=claims("staff@racco1.gov.ph", verified=False)):
            self.assertEqual(self.post().status_code, 401)

    def test_invalid_token_is_refused(self):
        with mock.patch(VERIFY, side_effect=ValueError("bad signature")):
            r = self.post()
        self.assertEqual(r.status_code, 401)
        # The reason must not leak back to the caller.
        self.assertNotIn("signature", str(r.data).lower())

    def test_missing_credential_is_refused(self):
        self.assertEqual(self.client.post("/api/auth/google/", {}, format="json").status_code, 401)

    def test_unknown_and_wrong_role_denials_are_indistinguishable(self):
        # A differing message would let an outsider enumerate staff addresses.
        with mock.patch(VERIFY, return_value=claims("stranger@gmail.com")):
            unknown = str(self.post().data)
        no_role = make_user("norole@racco1.gov.ph", Role.STAFF)
        no_role.role = None
        no_role.save(update_fields=["role"])
        with mock.patch(VERIFY, return_value=claims("norole@racco1.gov.ph", sub="sub-2")):
            roleless = str(self.post().data)
        self.assertEqual(unknown, roleless)

    @override_settings(GOOGLE_ALLOWED_DOMAINS=["racco1.gov.ph"])
    def test_domain_allowlist_blocks_outside_addresses(self):
        outsider = make_user("someone@gmail.com", Role.STAFF)
        with mock.patch(VERIFY, return_value=claims(outsider.email, sub="sub-3")):
            self.assertEqual(self.post().status_code, 401)

    @override_settings(GOOGLE_ALLOWED_DOMAINS=["racco1.gov.ph"])
    def test_domain_allowlist_admits_agency_addresses(self):
        with mock.patch(VERIFY, return_value=claims("staff@racco1.gov.ph")):
            self.assertEqual(self.post().status_code, 200)

    @override_settings(GOOGLE_OAUTH_CLIENT_ID="")
    def test_feature_off_refuses_cleanly(self):
        with mock.patch(VERIFY, return_value=claims("staff@racco1.gov.ph")) as verify:
            r = self.post()
        self.assertEqual(r.status_code, 401)
        verify.assert_not_called()

    # --- password login is untouched ------------------------------------

    def test_password_login_still_works_for_admin(self):
        self.admin.set_password("admin1234")
        self.admin.must_change_password = False
        self.admin.save()
        r = self.client.post("/api/auth/login/", {
            "email": "admin@racco1.gov.ph", "password": "admin1234"}, format="json")
        self.assertEqual(r.status_code, 200, r.data)
        self.assertIn("access", r.data)

    def test_password_login_still_works_for_staff(self):
        self.staff.set_password("staff1234")
        self.staff.must_change_password = False
        self.staff.save()
        r = self.client.post("/api/auth/login/", {
            "email": "staff@racco1.gov.ph", "password": "staff1234"}, format="json")
        self.assertEqual(r.status_code, 200, r.data)


class GoogleConfigEndpointTests(APITestCase):
    @override_settings(GOOGLE_OAUTH_CLIENT_ID="", GOOGLE_ALLOWED_DOMAINS=[])
    def test_reports_disabled_when_unconfigured(self):
        r = self.client.get("/api/auth/google/config/")
        self.assertEqual(r.status_code, 200)
        self.assertFalse(r.data["enabled"])

    @override_settings(GOOGLE_OAUTH_CLIENT_ID=GOOGLE_CLIENT_ID, GOOGLE_ALLOWED_DOMAINS=[])
    def test_reports_enabled_and_is_reachable_anonymously(self):
        # The login page has to read this before anyone has a token.
        r = self.client.get("/api/auth/google/config/")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.data["enabled"])
        self.assertEqual(r.data["client_id"], GOOGLE_CLIENT_ID)
