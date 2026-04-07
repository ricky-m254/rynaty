from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('curriculum', '0002_change_external_url_to_charfield'),
        ('school', '0001_initial'),
    ]

    operations = [
        # Make school_class nullable (templates don't need a specific class)
        migrations.AlterField(
            model_name='schemeofwork',
            name='school_class',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                to='school.schoolclass',
            ),
        ),
        # Make term nullable (templates don't need a specific term)
        migrations.AlterField(
            model_name='schemeofwork',
            name='term',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                to='school.term',
            ),
        ),
        # Add template flag
        migrations.AddField(
            model_name='schemeofwork',
            name='is_template',
            field=models.BooleanField(default=False),
        ),
        # Add template display name
        migrations.AddField(
            model_name='schemeofwork',
            name='template_name',
            field=models.CharField(
                blank=True,
                max_length=200,
                help_text='Friendly name shown in the template picker',
            ),
        ),
        # Add template description
        migrations.AddField(
            model_name='schemeofwork',
            name='template_description',
            field=models.TextField(
                blank=True,
                help_text='Describes what this template covers',
            ),
        ),
    ]
