import os

from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction


class Command(BaseCommand):
    help = "Create the initial workspace login from environment secrets, once."

    def handle(self, *args, **options):
        users = get_user_model()
        if users.objects.filter(is_active=True, is_superuser=True).exists():
            self.stdout.write("Workspace owner already exists.")
            return
        username = os.environ.get("DJANGO_SUPERUSER_USERNAME", "").strip()
        email = os.environ.get("DJANGO_SUPERUSER_EMAIL", "").strip()
        password = os.environ.get("DJANGO_SUPERUSER_PASSWORD", "")
        if not username or not password:
            raise CommandError("Set DJANGO_SUPERUSER_USERNAME and DJANGO_SUPERUSER_PASSWORD in Render's environment.")
        candidate = users(username=username, email=email)
        try:
            candidate.full_clean(exclude=["password"])
            validate_password(password, candidate)
        except ValidationError:
            raise CommandError("Choose a unique valid username and a stronger initial password in Render's environment.") from None
        with transaction.atomic():
            users.objects.create_superuser(username=username, email=email, password=password)
        self.stdout.write("Workspace owner created.")
