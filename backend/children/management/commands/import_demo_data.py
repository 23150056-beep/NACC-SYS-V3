"""Load the fictional caseload into a deployment database.

Intended for a Neon BRANCH that already carries the real user accounts. The
children come from `export_demo_data`; the accounts are whatever the branch
already holds, which is the reason for branching that database at all.

Every imported child is reassigned to a psychologist that exists here. The
fixture's assignee ids belong to the local machine and mean nothing on the
branch — left alone, every child would point at the wrong person or at nobody,
and a caseload nobody can see is not a demo.
"""
import json

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from accounts.models import Role
from children.models import Child


class Command(BaseCommand):
    help = "Load the fictional caseload and assign it to accounts that exist here."

    def add_arguments(self, parser):
        parser.add_argument("--fixture", required=True,
                            help="Path to the file written by export_demo_data.")
        parser.add_argument("--clear", action="store_true",
                            help="Delete existing children first.")
        parser.add_argument("--set-password", default="",
                            help="EMAIL:PASSWORD — give one account a known "
                                 "password, for demonstrating with.")

    @transaction.atomic
    def handle(self, *args, **options):
        User = get_user_model()
        psychologists = list(
            User.objects.filter(role__role_name=Role.PSYCHOLOGIST).order_by("pk"))
        if not psychologists:
            raise CommandError(
                "No psychologist accounts here. Importing would leave every "
                "child unassigned and invisible to everyone.")

        # Checked before loading anything, so a typo does not leave a
        # half-imported database behind.
        email = password = ""
        if options["set_password"]:
            email, _, password = options["set_password"].partition(":")
            if not User.objects.filter(email=email).exists():
                raise CommandError(f"No account here with the email {email}.")

        if options["clear"]:
            removed = Child.objects.count()
            Child.objects.all().delete()
            self.stdout.write(f"  cleared {removed} existing children")

        with open(options["fixture"], encoding="utf-8") as handle:
            rows = json.load(handle)
        self.stdout.write(f"  fixture holds {len(rows)} rows")
        call_command("loaddata", options["fixture"], verbosity=0)

        # Round-robin across whoever is really here. The fixture's assignee ids
        # are local and meaningless on this database.
        imported = list(Child.objects.order_by("pk"))
        for index, child in enumerate(imported):
            child.assigned_psychologist = psychologists[index % len(psychologists)]
        Child.objects.bulk_update(imported, ["assigned_psychologist"])

        if email:
            user = User.objects.get(email=email)
            user.set_password(password)
            user.must_change_password = False
            user.save()
            self.stdout.write(f"  password set for {email}")

        self.stdout.write(
            f"import_demo_data: {len(imported)} children across "
            f"{len(psychologists)} psychologists.")
