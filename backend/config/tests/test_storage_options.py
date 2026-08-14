"""Object-storage configuration.

Uploaded consent scans and psychological reports are the files this protects.
A wrong value here does not raise at boot — it fails the first time someone
uploads a real document, which is the worst possible moment to find out.
"""

from django.test import SimpleTestCase

from config.storages import s3_storage_options

R2 = {
    "AWS_STORAGE_BUCKET_NAME": "nacc-v3-media",
    "AWS_S3_ENDPOINT_URL": "https://abc123.r2.cloudflarestorage.com",
    "AWS_ACCESS_KEY_ID": "key",
    "AWS_SECRET_ACCESS_KEY": "secret",
}
AWS = {
    "AWS_STORAGE_BUCKET_NAME": "nacc-v3-media",
    "AWS_S3_REGION_NAME": "ap-southeast-1",
    "AWS_ACCESS_KEY_ID": "key",
    "AWS_SECRET_ACCESS_KEY": "secret",
}


class StorageOptionsTest(SimpleTestCase):
    def test_a_custom_endpoint_gets_path_addressing(self):
        """R2's endpoint is https://<account>.r2.cloudflarestorage.com. Virtual
        addressing would ask DNS for <bucket>.<account>.r2.cloudflarestorage.com,
        which does not exist, and every upload would fail to resolve."""
        self.assertEqual(s3_storage_options(R2)["addressing_style"], "path")

    def test_aws_keeps_virtual_addressing(self):
        self.assertEqual(s3_storage_options(AWS)["addressing_style"], "virtual")

    def test_addressing_style_can_still_be_overridden(self):
        env = {**R2, "AWS_S3_ADDRESSING_STYLE": "virtual"}
        self.assertEqual(s3_storage_options(env)["addressing_style"], "virtual")

    def test_region_defaults_to_auto_for_providers_without_regions(self):
        self.assertEqual(s3_storage_options(R2)["region_name"], "auto")

    def test_uploads_are_never_public(self):
        """The bucket holds child case files. A public-read ACL or an unsigned
        URL here would expose them to anyone who guessed a filename."""
        for env in (R2, AWS):
            opts = s3_storage_options(env)
            self.assertIsNone(opts["default_acl"])
            self.assertTrue(opts["querystring_auth"])
            self.assertGreater(opts["querystring_expire"], 0)

    def test_signed_urls_expire_quickly(self):
        self.assertLessEqual(s3_storage_options(R2)["querystring_expire"], 900)

    def test_uploads_never_overwrite(self):
        """Two consent scans saved under one name must not silently become
        one file — the second would destroy the first."""
        self.assertFalse(s3_storage_options(R2)["file_overwrite"])

    def test_no_endpoint_means_none_not_empty_string(self):
        """boto3 treats an empty endpoint_url as a malformed URL rather than
        as "use the default"."""
        self.assertIsNone(s3_storage_options(AWS)["endpoint_url"])
        self.assertIsNone(s3_storage_options({**AWS, "AWS_S3_ENDPOINT_URL": ""})["endpoint_url"])
