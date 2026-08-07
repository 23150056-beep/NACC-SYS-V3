"""Static-file storage backend for cloud deploys."""

from whitenoise.storage import CompressedManifestStaticFilesStorage


class WhiteNoiseStaticFilesStorage(CompressedManifestStaticFilesStorage):
    """Hashed + gzip/brotli-compressed static files served by WhiteNoise.

    `manifest_strict = False` is deliberate: with the default, *any* asset
    referenced by a template but missing from staticfiles.json raises at render
    time, which turns a cosmetic packaging slip into a 500 on a live deploy.
    Falling back to the unhashed name loses cache-busting for that one file and
    nothing else.
    """

    manifest_strict = False
