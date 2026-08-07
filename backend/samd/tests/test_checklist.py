from django.test import SimpleTestCase

from samd.checklist import CHECKLIST, TOTAL_ITEMS, validate


class ChecklistIntegrityTest(SimpleTestCase):
    """Structural checks against the official NACC-SAMD-GF-000 (June 2025)
    counts: KRA I=11, KRA II=51, KRA III=21, 83 total."""

    def test_validate_passes(self):
        self.assertTrue(validate())

    def test_three_kras(self):
        self.assertEqual(len(CHECKLIST), 3)
        self.assertEqual([kra["key"] for kra in CHECKLIST], ["I", "II", "III"])

    def test_item_counts_per_kra(self):
        counts = {kra["key"]: len(kra["items"]) for kra in CHECKLIST}
        self.assertEqual(counts, {"I": 11, "II": 51, "III": 21})

    def test_total_is_83(self):
        self.assertEqual(TOTAL_ITEMS, 83)
        self.assertEqual(sum(len(kra["items"]) for kra in CHECKLIST), 83)

    def test_keys_sequential_and_unique(self):
        seen = []
        for kra in CHECKLIST:
            numbers = [item["number"] for item in kra["items"]]
            self.assertEqual(numbers, list(range(1, len(kra["items"]) + 1)))
            for item in kra["items"]:
                self.assertEqual(item["key"], f'{kra["key"]}.{item["number"]}')
                seen.append(item["key"])
        self.assertEqual(len(seen), len(set(seen)))

    def test_every_indicator_non_empty(self):
        for kra in CHECKLIST:
            for item in kra["items"]:
                self.assertTrue(item["indicator"].strip(), item["key"])
