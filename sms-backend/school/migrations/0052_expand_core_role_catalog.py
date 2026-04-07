from django.db import migrations, models


ROLE_CHOICES = [
    ('TENANT_SUPER_ADMIN', 'Tenant Super Admin'),
    ('ADMIN', 'School Administrator'),
    ('ACCOUNTANT', 'Finance Manager'),
    ('TEACHER', 'Teaching Staff'),
    ('LIBRARIAN', 'School Librarian'),
    ('NURSE', 'School Nurse'),
    ('SECURITY', 'Security Staff'),
    ('COOK', 'Kitchen / Cook'),
    ('PARENT', 'Parent / Guardian'),
    ('STUDENT', 'Student'),
]


ROLE_SEEDS = [
    ('TENANT_SUPER_ADMIN', 'Tenant Super Admin'),
    ('ADMIN', 'School Administrator'),
    ('ACCOUNTANT', 'Finance Manager'),
    ('TEACHER', 'Teaching Staff'),
    ('LIBRARIAN', 'School Librarian'),
    ('NURSE', 'School Nurse'),
    ('SECURITY', 'Security Staff'),
    ('COOK', 'Kitchen / Cook'),
    ('PARENT', 'Parent / Guardian'),
    ('STUDENT', 'Student'),
]


def seed_roles(apps, schema_editor):
    Role = apps.get_model('school', 'Role')
    for name, description in ROLE_SEEDS:
        Role.objects.get_or_create(name=name, defaults={'description': description})


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('school', '0051_student_enforce_ulid_constraints'),
    ]

    operations = [
        migrations.AlterField(
            model_name='role',
            name='name',
            field=models.CharField(choices=ROLE_CHOICES, max_length=50, unique=True),
        ),
        migrations.RunPython(seed_roles, noop_reverse),
    ]
