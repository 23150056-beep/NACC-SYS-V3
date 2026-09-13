"""A test run must not write into the developer's media directory.

Django isolates the database for a test run and does NOT isolate file
storage. `MEDIA_ROOT` stays pointed at `backend/media`, so every test that
saves a FileField writes a real file there and nothing ever removes it.

Found by counting: 1,527 files under `media/case-referrals` for 42 rows —
1,485 orphans, every one of them left by a test. It ran for months because
the directory is gitignored, so the growth was invisible to `git status`, and
because a leak is not a failure: nothing goes red, the disk just fills.

Six test modules had already noticed and each made its own temporary
directory with `override_settings`. None of them cleaned it up, and the
modules that write the most files — the referral seeders — were never among
them. A guard applied per file is a guard somebody forgets, so this is done
once for the whole run in `config.test_runner`.
"""
from pathlib import Path

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.test import SimpleTestCase, TestCase

REPO_MEDIA = Path(settings.BASE_DIR) / "media"


class MediaRootIsIsolatedTest(SimpleTestCase):
    def test_it_is_not_the_working_copys_media_directory(self):
        self.assertNotEqual(REPO_MEDIA.resolve(),
                            Path(settings.MEDIA_ROOT).resolve())

    def test_a_saved_file_lands_outside_the_working_copy(self):
        name = default_storage.save("isolation-probe.txt", ContentFile(b"probe"))
        try:
            written = Path(default_storage.path(name)).resolve()
            self.assertFalse(
                written.is_relative_to(REPO_MEDIA.resolve()),
                f"a test wrote into the repository: {written}")
        finally:
            default_storage.delete(name)


class TheReferralSeederWritesOutsideTheWorkingCopyTest(TestCase):
    """The specific path that leaked, kept honest by going through it."""

    def test_seeded_referrals_do_not_land_in_the_repository(self):
        from accounts.models import Role
        from children.models import Child
        from clinical import demo_referrals
        from clinical.models import CaseReferral
        from django.contrib.auth import get_user_model

        psy = get_user_model().objects.create_user(
            email="p@racco1.gov.ph", username="p", password="pass1234",
            role=Role.objects.create(role_name=Role.PSYCHOLOGIST))
        child = Child.objects.create(fullname="Ana Lopez", assigned_psychologist=psy)
        demo_referrals.install_referrals([child])

        written = Path(CaseReferral.objects.get(child=child).file.path).resolve()
        self.assertFalse(
            written.is_relative_to(REPO_MEDIA.resolve()),
            f"the seeder wrote into the repository: {written}")
