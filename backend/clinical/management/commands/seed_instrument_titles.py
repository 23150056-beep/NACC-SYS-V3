"""Seed the shared (agency-wide) instrument title catalog (idempotent).

Titles and category/audience metadata only — never instrument items, scales,
or scoring keys (copyright policy §2, see InstrumentCatalog docstring).
"""
from django.core.management.base import BaseCommand
from clinical.models import InstrumentCatalog

# RACCO I's official pre-assessment battery (titles only — copyright policy).
TITLES = [
    # For children
    ("Children's Problem Checklist", "behavioral", "child"),
    ("Adolescent Problem Checklist", "behavioral", "child"),
    ("Multiscore Depression Inventory for Children", "personality", "child"),
    ("Slosson Intelligence Test", "cognitive", "child"),
    ("Children's Apperception Test", "projective", "child"),
    # Used with both children and prospective adoptive parents
    ("Raven's Progressive Matrices", "cognitive", "both"),
    ("Sentence Completion Series", "projective", "both"),
    # For prospective adoptive parents
    ("Basic Personality Inventory", "personality", "adoptive_parent"),
    ("Marital Satisfaction Inventory", "other", "adoptive_parent"),
    ("Thematic Apperception Test", "projective", "adoptive_parent"),
]


class Command(BaseCommand):
    help = "Seed the shared (agency-wide) instrument title catalog. Idempotent."

    def handle(self, *args, **options):
        created = 0
        for title, category, audience in TITLES:
            _, was_created = InstrumentCatalog.objects.get_or_create(
                title=title, owner=None,
                defaults={"category": category, "audience": audience})
            created += int(was_created)
        self.stdout.write(self.style.SUCCESS(
            f"seed_instrument_titles: {created} created, {len(TITLES) - created} already present."))
