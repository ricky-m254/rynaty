from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django_tenants.utils import schema_context

User = get_user_model()

class Command(BaseCommand):
    help = 'Creates a superuser inside a specific Tenant Schema.'

    def add_arguments(self, parser):
        parser.add_argument('--schema_name', type=str, help='Target Schema Name')
        parser.add_argument('--username', type=str, help='Admin Username')
        parser.add_argument('--password', type=str, help='Admin Password')
        parser.add_argument('--email', type=str, help='Admin Email')

    def handle(self, *args, **options):
        schema_name = options['schema_name']
        username = options['username']
        password = options['password']
        email = options.get('email', 'admin@school.com')

        if not all([schema_name, username, password]):
            self.stdout.write(self.style.ERROR("Missing arguments."))
            return

        with schema_context(schema_name):
            if User.objects.filter(username=username).exists():
                self.stdout.write(self.style.ERROR("User already exists in this schema."))
                return

            User.objects.create_superuser(username=username, password=password, email=email)
            self.stdout.write(self.style.SUCCESS(
                f" Admin user '{username}' created in schema '{schema_name}'."
            ))
