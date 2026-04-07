from django.db import migrations


ROLES = [
    ('PARENT',  'Parent / Guardian'),
    ('STUDENT', 'Student'),
    ('LIBRARIAN', 'School Librarian'),
    ('NURSE',   'School Nurse'),
]


def seed_roles(apps, schema_editor):
    Role = apps.get_model('school', 'Role')
    for name, description in ROLES:
        Role.objects.get_or_create(name=name, defaults={'description': description})


def reverse_roles(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('school', '0039_add_student_transfer'),
    ]

    operations = [
        migrations.RunPython(seed_roles, reverse_roles),
    ]
