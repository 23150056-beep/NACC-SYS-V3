"""The seeded referral has to be a file the app would accept.

It was written as .txt, and CaseReferralSerializer accepts pdf, doc and docx
only. So a demo child carried a referral that satisfied the booking gate and
that the upload form would have refused — two different answers to "is this a
valid case referral", from one system, about one file.

That is the same fault as a seeder whose rows the endpoint rejects, just
quieter: nothing breaks until somebody tries to replace one.

No PDF library is installed and adding one for a demo fixture would be a poor
trade, so the bytes are assembled here. A PDF's trailer points at a table of
byte offsets and a reader will refuse the file if they are wrong, which is
exactly the kind of thing that looks fine until something opens it — hence the
structural assertions below rather than "it starts with %PDF".
"""
from django.contrib.auth import get_user_model

from accounts.models import Role
from children.models import Child
from clinical import demo_referrals
from clinical.models import CaseReferral
from clinical.serializers import ALLOWED_REPORT_EXTENSIONS
from django.test import TestCase

User = get_user_model()


class SeededReferralIsAPdfTest(TestCase):
    def setUp(self):
        self.psy = User.objects.create_user(
            email="p@racco1.gov.ph", username="p", password="pass1234",
            role=Role.objects.create(role_name=Role.PSYCHOLOGIST))
        self.child = Child.objects.create(fullname="Ana Lopez",
                                          assigned_psychologist=self.psy)
        demo_referrals.install_referrals([self.child])
        self.referral = CaseReferral.objects.get(child=self.child)

    def _bytes(self):
        self.referral.file.open("rb")
        try:
            return self.referral.file.read()
        finally:
            self.referral.file.close()

    def test_the_extension_is_one_the_upload_form_accepts(self):
        ext = self.referral.original_filename.rsplit(".", 1)[-1].lower()
        self.assertIn(ext, ALLOWED_REPORT_EXTENSIONS)

    def test_it_is_a_pdf_by_its_bytes_not_just_its_name(self):
        raw = self._bytes()
        self.assertTrue(raw.startswith(b"%PDF-"), raw[:20])
        self.assertTrue(raw.rstrip().endswith(b"%%EOF"), raw[-20:])

    def test_the_cross_reference_offsets_are_real(self):
        """A reader follows startxref to the table and the table to each
        object. Offsets computed by hand are the part that silently rots."""
        raw = self._bytes()
        marker = raw.rindex(b"startxref")
        start = int(raw[marker + len(b"startxref"):].split(b"%%EOF")[0].strip())
        self.assertEqual(b"xref", raw[start:start + 4],
                         "startxref does not point at the xref table")

        # Every offset in the table must land on "<n> 0 obj".
        table = raw[start:].split(b"\n")
        offsets = [line for line in table if line.rstrip().endswith(b" n")]
        self.assertGreaterEqual(len(offsets), 4, "too few objects for a page")
        for i, line in enumerate(offsets, start=1):
            at = int(line.split()[0])
            self.assertEqual(f"{i} 0 obj".encode(), raw[at:at + len(f"{i} 0 obj")],
                             f"object {i} is not at the offset the table claims")

    def test_the_child_is_named_in_it(self):
        self.assertIn(b"Ana Lopez", self._bytes())

    def test_it_says_it_is_invented(self):
        self.assertIn(b"DEMONSTRATION", self._bytes())
