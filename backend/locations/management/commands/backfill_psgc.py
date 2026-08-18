from django.core.management.base import BaseCommand
from django.db.models import Q

from children.models import Child
from locations.models import Barangay, Municipality, Province


def _norm(value):
    """Loose enough to match what people actually typed, strict enough not to
    guess. Case and surrounding whitespace are noise; anything else is not."""
    return (value or "").strip().casefold()


class Command(BaseCommand):
    help = ("Fill in PSGC codes on existing child records by matching the "
            "province/municipality/barangay text already stored. Reports what "
            "it could not match; changes nothing else.")

    def add_arguments(self, parser):
        parser.add_argument(
            "--apply", action="store_true",
            help="Write the matches. Without it this is a dry run.")
        parser.add_argument(
            "--recheck", action="store_true",
            help=("Also re-examine records that already carry codes. Off by "
                  "default: a code chosen by a person in the form is better "
                  "evidence than a text match, and must not be recomputed "
                  "away just because the wording differs."))

    def handle(self, *args, **options):
        apply_changes = options["apply"]
        provinces = {_norm(p.name): p for p in Province.objects.all()}
        municipalities = {}
        for m in Municipality.objects.select_related("province"):
            municipalities.setdefault(m.province.psgc_code, {})[_norm(m.name)] = m
        barangays = {}
        for b in Barangay.objects.select_related("municipality"):
            barangays.setdefault(b.municipality.psgc_code, {})[_norm(b.name)] = b

        rows = Child.objects.filter(
            Q(province__gt="") | Q(municipality__gt="") | Q(barangay__gt=""))
        if not options["recheck"]:
            # Only records with nothing attached yet. This is what makes the
            # command safe to run on every deploy: an address someone picked in
            # the form is left exactly as they picked it.
            rows = rows.filter(psgc_province="", psgc_municipality="", psgc_barangay="")
        matched = {"province": 0, "municipality": 0, "barangay": 0}
        unmatched = []
        touched = []

        for child in rows:
            p = provinces.get(_norm(child.province))
            m = municipalities.get(p.psgc_code, {}).get(_norm(child.municipality)) if p else None
            b = barangays.get(m.psgc_code, {}).get(_norm(child.barangay)) if m else None

            child.psgc_province = p.psgc_code if p else ""
            child.psgc_municipality = m.psgc_code if m else ""
            child.psgc_barangay = b.psgc_code if b else ""
            if p: matched["province"] += 1
            if m: matched["municipality"] += 1
            if b: matched["barangay"] += 1

            # Only the levels the record actually filled in count as misses —
            # a blank barangay is an incomplete address, not a failed match.
            missed = [
                label for label, text, hit in (
                    ("province", child.province, p),
                    ("municipality", child.municipality, m),
                    ("barangay", child.barangay, b))
                if (text or "").strip() and not hit
            ]
            if missed:
                unmatched.append((child, missed))
            touched.append(child)

        if apply_changes and touched:
            Child.objects.bulk_update(
                touched, ["psgc_province", "psgc_municipality", "psgc_barangay"])

        self.stdout.write(f"records with an address: {len(touched)}")
        for level in ("province", "municipality", "barangay"):
            self.stdout.write(f"  matched {level}: {matched[level]}")

        if unmatched:
            self.stdout.write(self.style.WARNING(
                f"\n{len(unmatched)} record(s) a human needs to look at:"))
            for child, missed in unmatched[:50]:
                where = " / ".join(x for x in (child.province, child.municipality, child.barangay) if x)
                self.stdout.write(f"  #{child.id} {child.fullname}: {where}  (no match: {', '.join(missed)})")
            if len(unmatched) > 50:
                self.stdout.write(f"  … and {len(unmatched) - 50} more")
            self.stdout.write(
                "\nThese keep the text they already had. Open each record and "
                "re-pick the address to attach a code.")
        else:
            self.stdout.write(self.style.SUCCESS("\nEverything matched."))

        if not apply_changes:
            self.stdout.write(self.style.WARNING("\nDry run — nothing written. Re-run with --apply."))
