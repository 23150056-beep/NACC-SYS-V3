"""Guards against deployments that look healthy and are not.

All three of these were real. A demo deployment on 27 Aug 2026 came up green
and was quietly broken in three separate ways, none of which was visible from
outside:

* `DATABASE_URL` was never set, so Django fell through to the zero-config
  SQLite path. `seed_initial_data` then seeded a fresh administrator into a
  file on the container's disk — which Render destroys on every deploy and
  every wake from sleep. `/healthz/` reported `{"database": "ok"}` throughout,
  because SQLite *is* a working database.
* `CORS_ALLOWED_ORIGINS` was never set, so the browser blocked every request
  while `curl` worked perfectly.

The failures share a shape: the service reports healthy, and the application is
broken. These guards make each one say so.
"""
from django.test import SimpleTestCase, TestCase

from config.guards import cors_is_unconfigured, sqlite_fallback_is_a_mistake


class SqliteFallbackTest(SimpleTestCase):
    def test_a_deployment_without_a_database_url_is_a_mistake(self):
        self.assertTrue(sqlite_fallback_is_a_mistake(
            debug=False, database_url="", db_engine="sqlite"))

    def test_local_development_is_fine(self):
        # SQLite with DEBUG=True is the zero-config path, and it is correct.
        self.assertFalse(sqlite_fallback_is_a_mistake(
            debug=True, database_url="", db_engine="sqlite"))

    def test_a_database_url_is_fine(self):
        self.assertFalse(sqlite_fallback_is_a_mistake(
            debug=False, database_url="postgresql://host/db", db_engine="sqlite"))

    def test_an_explicit_postgres_engine_is_fine(self):
        # The on-premises path predating V3 sets DB_ENGINE rather than a URL.
        self.assertFalse(sqlite_fallback_is_a_mistake(
            debug=False, database_url="", db_engine="postgres"))

    def test_whitespace_is_not_a_database_url(self):
        self.assertTrue(sqlite_fallback_is_a_mistake(
            debug=False, database_url="   ", db_engine="sqlite"))


class CorsGuardTest(SimpleTestCase):
    LOCAL = ["http://localhost:5173", "http://127.0.0.1:5173"]

    def test_a_deployment_still_on_the_localhost_default_is_unconfigured(self):
        self.assertTrue(cors_is_unconfigured(debug=False, origins=self.LOCAL))

    def test_an_empty_list_is_unconfigured(self):
        self.assertTrue(cors_is_unconfigured(debug=False, origins=[]))

    def test_a_real_origin_is_configured(self):
        self.assertFalse(cors_is_unconfigured(
            debug=False, origins=["https://nacc-v3-demo-web.onrender.com"]))

    def test_local_development_is_fine(self):
        self.assertFalse(cors_is_unconfigured(debug=True, origins=self.LOCAL))

    def test_a_real_origin_alongside_the_local_ones_is_configured(self):
        self.assertFalse(cors_is_unconfigured(
            debug=False, origins=self.LOCAL + ["https://demo.example.gov.ph"]))


class HealthzTest(TestCase):
    """`{"database": "ok"}` did not distinguish Neon from an ephemeral SQLite
    file. It has to name what it reached."""

    def test_reports_ok(self):
        res = self.client.get("/healthz/")
        self.assertEqual(200, res.status_code)
        self.assertEqual("ok", res.json()["status"])

    def test_names_the_database_engine(self):
        body = self.client.get("/healthz/").json()
        self.assertIn("engine", body)
        self.assertIn("sqlite", body["engine"])

    def test_names_the_host_so_the_wrong_database_is_visible(self):
        body = self.client.get("/healthz/").json()
        self.assertIn("host", body)

    def test_never_leaks_a_password(self):
        # The host is deployment detail; the credential is not.
        raw = self.client.get("/healthz/").content.decode().lower()
        for secret in ("password", "@", "://"):
            self.assertNotIn(secret, raw)
