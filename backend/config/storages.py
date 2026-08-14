"""Storage configuration for cloud deploys."""

import os

from whitenoise.storage import CompressedManifestStaticFilesStorage


def s3_storage_options(env=None):
    """Build the S3Storage OPTIONS for whichever provider is configured.

    Lives here rather than inline in settings so it can be tested: the
    addressing-style rule below is exactly the kind of thing that is silently
    wrong until someone uploads a real consent scan.
    """
    env = os.environ if env is None else env

    # AWS S3 needs virtual-hosted addressing. Every other S3-compatible
    # provider is reached through an explicit endpoint where the bucket belongs
    # in the PATH — Cloudflare R2's endpoint is
    # https://<account>.r2.cloudflarestorage.com, and virtual style would ask
    # DNS for <bucket>.<account>.r2.cloudflarestorage.com, which does not
    # exist. So: an endpoint_url means path, no endpoint_url means AWS.
    endpoint = env.get("AWS_S3_ENDPOINT_URL") or None
    addressing = env.get("AWS_S3_ADDRESSING_STYLE") or ("path" if endpoint else "virtual")

    return {
        "bucket_name": env.get("AWS_STORAGE_BUCKET_NAME"),
        # R2 has no regions; "auto" is what it expects and what AWS ignores.
        "region_name": env.get("AWS_S3_REGION_NAME", "auto"),
        "endpoint_url": endpoint,
        "access_key": env.get("AWS_ACCESS_KEY_ID"),
        "secret_key": env.get("AWS_SECRET_ACCESS_KEY"),
        # Child data: the bucket must never be publicly readable, and any URL
        # the storage backend hands out must be short-lived and signed.
        "default_acl": None,
        "querystring_auth": True,
        "querystring_expire": int(env.get("AWS_S3_URL_EXPIRY", "300")),
        "file_overwrite": False,
        "signature_version": "s3v4",
        "addressing_style": addressing,
    }


class WhiteNoiseStaticFilesStorage(CompressedManifestStaticFilesStorage):
    """Hashed + gzip/brotli-compressed static files served by WhiteNoise.

    `manifest_strict = False` is deliberate: with the default, *any* asset
    referenced by a template but missing from staticfiles.json raises at render
    time, which turns a cosmetic packaging slip into a 500 on a live deploy.
    Falling back to the unhashed name loses cache-busting for that one file and
    nothing else.
    """

    manifest_strict = False
