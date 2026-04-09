from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('library', '0003_librarymember_student'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunSQL(
                    sql="ALTER TABLE library_libraryresource ADD COLUMN IF NOT EXISTS digital_url varchar(1000) NOT NULL DEFAULT ''",
                    reverse_sql="ALTER TABLE library_libraryresource DROP COLUMN IF EXISTS digital_url",
                ),
            ],
            state_operations=[
                migrations.AddField(
                    model_name='libraryresource',
                    name='digital_url',
                    field=models.URLField(blank=True, help_text='Online access link for digital/open-access resources', max_length=1000),
                ),
            ],
        ),
    ]
