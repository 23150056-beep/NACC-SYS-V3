import json
from pathlib import Path

from django.core.management.base import BaseCommand
from django.db import transaction

from locations.models import Barangay, Municipality, Province

DATA = Path(__file__).resolve().parents[2] / "data" / "psgc_region1.json"


class Command(BaseCommand):
    help = "Load PSGC provinces, cities/municipalities and barangays from the bundled dataset."

    def add_arguments(self, parser):
        parser.add_argument(
            "--file", default=str(DATA),
            help="Path to a PSGC JSON file (defaults to the bundled Region I subset).")

    @transaction.atomic
    def handle(self, *args, **options):
        payload = json.loads(Path(options["file"]).read_text(encoding="utf-8"))
        self.stdout.write(f"Release: {payload.get('psgc_release', 'unknown')}")

        # update_or_create keyed on the PSGC code, so re-running against a newer
        # release renames places in situ rather than duplicating them — and a
        # child record pointing at a code keeps pointing at the same place.
        prov_by_code, made, seen = {}, 0, 0
        for row in payload["provinces"]:
            obj, created = Province.objects.update_or_create(
                psgc_code=row["code"], defaults={"name": row["name"]})
            prov_by_code[row["code"]] = obj
            made += created; seen += 1
        self.stdout.write(f"  provinces:       {seen:>5} ({made} new)")

        muni_by_code, made, seen = {}, 0, 0
        for row in payload["municipalities"]:
            obj, created = Municipality.objects.update_or_create(
                psgc_code=row["code"],
                defaults={"name": row["name"], "province": prov_by_code[row["province"]]})
            muni_by_code[row["code"]] = obj
            made += created; seen += 1
        self.stdout.write(f"  municipalities:  {seen:>5} ({made} new)")

        made = seen = 0
        for row in payload["barangays"]:
            _, created = Barangay.objects.update_or_create(
                psgc_code=row["code"],
                defaults={"name": row["name"], "municipality": muni_by_code[row["municipality"]]})
            made += created; seen += 1
        self.stdout.write(f"  barangays:       {seen:>5} ({made} new)")
        self.stdout.write(self.style.SUCCESS("PSGC loaded."))
