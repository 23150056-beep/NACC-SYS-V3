"""Flag self-reports that were submitted before flagging existed.

Idempotent: the unique constraint on (invite, question, source) means a second
run creates nothing new. That matters because the phrase list grows — re-running
after adding a phrase is how the list gets applied to what is already there.

The model pass is opt-in. 122 records at roughly two seconds each is four
minutes; the lexicon pass is instant.

    manage.py scan_self_reports                # lexicon only
    manage.py scan_self_reports --with-model   # also ask the local model
"""
from django.core.management.base import BaseCommand

from clinical.models import OpinionnaireInvite, SelfReportFlag
from clinical.self_report_detection import detect_concerns


class Command(BaseCommand):
    help = "Flag distress in self-reports already in the database."

    def add_arguments(self, parser):
        parser.add_argument("--with-model", action="store_true",
                            help="Also run the local model over each report.")
        parser.add_argument("--limit", type=int, default=0,
                            help="Stop after this many invites (0 = all).")

    def handle(self, *args, **options):
        from clinical import self_report_model_check

        qs = (OpinionnaireInvite.objects
              .filter(status=OpinionnaireInvite.SUBMITTED)
              .select_related("child").order_by("pk"))
        if options["limit"]:
            qs = qs[:options["limit"]]

        scanned = created = 0
        for invite in qs:
            scanned += 1
            for question, answer in (invite.answers or {}).items():
                for hit in detect_concerns(question, answer):
                    _, made = SelfReportFlag.objects.get_or_create(
                        invite=invite, question=question,
                        source=SelfReportFlag.LEXICON,
                        defaults={"child": invite.child, "answer": answer,
                                  "matched": hit["phrase"]})
                    created += int(made)
                    break
            if options["with_model"]:
                self_report_model_check.run_model_check(invite.pk)

        self.stdout.write(
            f"scan_self_reports: {scanned} submissions, {created} new flags.")
