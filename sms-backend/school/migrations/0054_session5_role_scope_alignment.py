from django.db import migrations, models


ROLE_CHOICES = [
    ("TENANT_SUPER_ADMIN", "Tenant Super Admin"),
    ("ADMIN", "School Administrator"),
    ("PRINCIPAL", "School Principal"),
    ("DEPUTY_PRINCIPAL", "Deputy Principal"),
    ("HOD", "Head of Department"),
    ("ACCOUNTANT", "Finance Manager"),
    ("BURSAR", "School Bursar"),
    ("HR_OFFICER", "HR Officer"),
    ("REGISTRAR", "Registrar"),
    ("TEACHER", "Teaching Staff"),
    ("LIBRARIAN", "School Librarian"),
    ("NURSE", "School Nurse"),
    ("SECURITY", "Security Staff"),
    ("SECURITY_GUARD", "Security Guard"),
    ("COOK", "Kitchen / Cook"),
    ("STORE_CLERK", "Store Clerk"),
    ("PARENT", "Parent / Guardian"),
    ("STUDENT", "Student"),
    ("ALUMNI", "Alumni"),
]


ROLE_SEEDS = ROLE_CHOICES


def seed_roles(apps, schema_editor):
    Role = apps.get_model("school", "Role")
    for name, description in ROLE_SEEDS:
        Role.objects.get_or_create(name=name, defaults={"description": description})


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("school", "0053_userprofile_force_password_change"),
    ]

    operations = [
        migrations.AlterField(
            model_name="role",
            name="name",
            field=models.CharField(choices=ROLE_CHOICES, max_length=50, unique=True),
        ),
        migrations.RunPython(seed_roles, noop_reverse),
    ]
