from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import connection, transaction


class Command(BaseCommand):
    help = "Prepare a private PostgreSQL schema before applying Django migrations."

    def handle(self, *args, **options):
        schema = settings.DATABASE_SCHEMA
        if not schema:
            return
        quoted = connection.ops.quote_name(schema)
        with transaction.atomic(), connection.cursor() as cursor:
            cursor.execute(f"CREATE SCHEMA IF NOT EXISTS {quoted}")
            cursor.execute(f"REVOKE ALL ON SCHEMA {quoted} FROM PUBLIC")
            cursor.execute("SELECT rolname FROM pg_roles WHERE rolname IN ('anon', 'authenticated')")
            for (name,) in cursor.fetchall():
                role = connection.ops.quote_name(name)
                cursor.execute(f"REVOKE ALL ON SCHEMA {quoted} FROM {role}")
                for kind in ("TABLES", "SEQUENCES", "FUNCTIONS"):
                    cursor.execute(f"ALTER DEFAULT PRIVILEGES IN SCHEMA {quoted} REVOKE ALL ON {kind} FROM {role}")
        self.stdout.write("Private application schema is ready.")
