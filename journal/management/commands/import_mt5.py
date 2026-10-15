from pathlib import Path
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from journal.importer import ImportProblem, discover_reports, import_reports


class Command(BaseCommand):
    help = "Import existing MT5 report pairs; this never runs a backtest or modifies MT5 files."

    def add_arguments(self, parser):
        parser.add_argument("paths", nargs="*", type=Path)
        parser.add_argument("--latest", action="store_true", help="Latest report per pair and timeframe in each strategy/entry folder")
        parser.add_argument("--all", action="store_true", help="All existing reports")

    def handle(self, *args, **options):
        paths = options["paths"]
        if not paths:
            if not (options["latest"] or options["all"]):
                raise CommandError("Supply CSV paths, --latest, or --all.")
            paths = discover_reports(settings.MT5_REPORTS_DIR, latest=not options["all"])
        imported, skipped, failed = 0, 0, 0
        for path in paths:
            html = path.with_suffix(".html")
            try:
                run, created = import_reports(path.read_bytes(), path.name, html.read_bytes() if html.exists() else b"", html.name, source_reference=str(path))
                imported += created
                skipped += not created
                self.stdout.write(f"{'Imported' if created else 'Already saved'}: {run.strategy} / {run.symbol} {run.timeframe} / {run.short_id}")
            except (ImportProblem, OSError) as exc:
                failed += 1
                self.stderr.write(f"Could not import {path.name}: {exc}")
        self.stdout.write(f"{imported} imported; {skipped} duplicates skipped; {failed} failed.")
        if failed:
            raise CommandError("Some reports could not be imported. See messages above.")
