from django.core.management.base import BaseCommand
from django.db import transaction
from journal.importer import ImportProblem, point0_details
from journal.models import BacktestRun, Trade


class Command(BaseCommand):
    help = "Recover point 0 labels explicitly present in stored reports; never guess missing labels."

    def handle(self, *args, **options):
        changed = []
        for trade in Trade.objects.filter(point0_label="").iterator():
            try:
                label, at, source = point0_details(trade.raw)
            except ImportProblem as exc:
                self.stderr.write(f"Run {trade.run_id}, trade {trade.number}: {exc}")
                continue
            if label:
                trade.point0_label, trade.point0_label_at, trade.point0_label_source = label, at, source
                changed.append(trade)
        with transaction.atomic():
            Trade.objects.bulk_update(changed, ["point0_label", "point0_label_at", "point0_label_source"], batch_size=400)
            for run in BacktestRun.objects.all():
                missing = run.trades.filter(point0_label="").count()
                warnings = [w for w in run.import_warnings if not w.startswith("Point 0 label was not recorded for")]
                if missing:
                    warnings.append(f"Point 0 label was not recorded for {missing} trades. Rerun the updated MT5 script and import its new reports to fill those labels.")
                if warnings != run.import_warnings:
                    run.import_warnings = warnings
                    run.save(update_fields=["import_warnings"])
        self.stdout.write(f"Recovered {len(changed)} explicitly recorded labels.")
        self.stdout.write(f"{Trade.objects.filter(point0_label='').count()} trades still require newly generated MT5 reports.")
