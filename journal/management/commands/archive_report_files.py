import hashlib

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from journal.models import BacktestRun, ReportFile


class Command(BaseCommand):
    help = "Copy original report bytes into the database for transfer to diskless hosting."

    def handle(self, *args, **options):
        count = total = 0
        with transaction.atomic():
            for run in BacktestRun.objects.all().iterator():
                for field, expected in ((run.csv_report, run.csv_sha256), (run.html_report, run.html_sha256)):
                    if not field:
                        continue
                    with field.open("rb") as source:
                        content = source.read()
                    digest = hashlib.sha256(content).hexdigest()
                    if expected and digest != expected:
                        raise CommandError(f"Source checksum mismatch for run {run.short_id}; no reports were archived.")
                    report, created = ReportFile.objects.get_or_create(
                        name=field.name,
                        defaults={"content": content, "byte_count": len(content), "sha256": digest},
                    )
                    if report.sha256 != digest or report.byte_count != len(content):
                        raise CommandError(f"Conflicting archived source for run {run.short_id}; no reports were archived.")
                    count += created
                    total += len(content)
        self.stdout.write(f"Archived {count} new report files. Referenced reports total {total:,} bytes; filesystem originals are preserved.")
