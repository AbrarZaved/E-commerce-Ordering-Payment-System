import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

User = get_user_model()


class Command(BaseCommand):
    help = "Create a default admin (superuser) from env vars or CLI options."

    def add_arguments(self, parser):
        parser.add_argument("--email", default=os.environ.get("ADMIN_EMAIL", "admin@example.com"))
        parser.add_argument("--password", default=os.environ.get("ADMIN_PASSWORD", "admin12345"))

    def handle(self, *args, **options):
        email = options["email"].lower()
        password = options["password"]
        user, created = User.objects.get_or_create(
            email=email,
            defaults={"full_name": "Site Admin", "is_staff": True, "is_superuser": True},
        )
        if created:
            user.set_password(password)
            user.is_staff = True
            user.is_superuser = True
            user.save()
            self.stdout.write(self.style.SUCCESS(f"Created admin {email}"))
        else:
            self.stdout.write(self.style.WARNING(f"Admin {email} already exists"))
