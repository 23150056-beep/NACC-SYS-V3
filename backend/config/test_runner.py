"""A test run that leaves nothing behind on disk.

Django gives a test run its own database and does not give it its own file
storage: `MEDIA_ROOT` still points at `backend/media`, so a test that saves a
FileField writes a real file into the working copy and nothing removes it.

That leaked 1,485 files into `media/case-referrals` — 1,527 on disk for 42
rows — before anyone counted. It survived because it is a leak rather than a
failure: nothing turns red, `git status` stays clean because the directory is
ignored, and the only symptom is a folder quietly growing.

Six test modules had already hit this and each made its own `mkdtemp` with
`override_settings`, none of them cleaning up afterwards, and the modules
writing the most files were not among them. A precaution that has to be
remembered per file is one that gets forgotten, so it is done here once for
the whole run.

`override_settings` rather than assigning to `settings.MEDIA_ROOT`: the
assignment sends no `setting_changed` signal, so the storage backend keeps
its cached location and carries on writing to the old path.
"""
import shutil
import tempfile

from django.test import override_settings
from django.test.runner import DiscoverRunner


class IsolatedMediaRunner(DiscoverRunner):
    def setup_test_environment(self, **kwargs):
        super().setup_test_environment(**kwargs)
        self._media_dir = tempfile.mkdtemp(prefix="nacc-test-media-")
        self._media_override = override_settings(MEDIA_ROOT=self._media_dir)
        self._media_override.enable()

    def teardown_test_environment(self, **kwargs):
        self._media_override.disable()
        # Removed rather than left for the operating system to tidy: a full
        # run writes a few thousand files, and %TEMP% is where the previous
        # attempt at this quietly piled them up.
        shutil.rmtree(self._media_dir, ignore_errors=True)
        super().teardown_test_environment(**kwargs)
