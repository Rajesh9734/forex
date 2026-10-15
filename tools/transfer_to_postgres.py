"""Transfer a private journal fixture to a fresh Supabase application schema."""
import argparse
import getpass
import os
from pathlib import Path
import sys


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("fixture", type=Path)
    args = parser.parse_args()
    if not args.fixture.is_file():
        parser.error("The journal fixture does not exist.")
    database_url = getpass.getpass("Supabase Session pooler PostgreSQL URL (hidden): ").strip()
    if not database_url.startswith(("postgres://", "postgresql://")):
        parser.error("Provide a PostgreSQL connection URL.")
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    os.environ["DJANGO_SETTINGS_MODULE"] = "config.settings"
    os.environ["DATABASE_URL"] = database_url
    os.environ["DJANGO_DB_SCHEMA"] = "forex_backtest"
    os.environ["DJANGO_REPORT_STORAGE"] = "database"

    connection = None
    try:
        import django
        django.setup()
        from django.conf import settings
        from django.core.management import call_command
        from django.db import connection
        settings.DATABASES["default"].setdefault("OPTIONS", {})["sslmode"] = "require"
        call_command("prepare_database")
        call_command("migrate", interactive=False, verbosity=0)
        from journal.models import BacktestRun, ReportFile, StrategyVersion, Trade
        if any(model.objects.exists() for model in (BacktestRun, ReportFile, StrategyVersion, Trade)):
            print("Stopped: the target journal is not empty. No fixture records were imported.", file=sys.stderr)
            return 1
        call_command("loaddata", str(args.fixture.resolve()), verbosity=0)
        print(f"Transferred {BacktestRun.objects.count()} runs, {Trade.objects.count()} trades and {ReportFile.objects.count()} report files.")
        return 0
    except Exception:
        # Connection exceptions may contain URL details. Keep the entered secret
        # out of terminal logs; diagnose with the Supabase dashboard if needed.
        print("Transfer failed. Check the connection, database password and fixture; the local journal was not changed.", file=sys.stderr)
        return 1
    finally:
        if connection is not None:
            connection.close()


if __name__ == "__main__":
    raise SystemExit(main())
