from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("school", "0009_admissions_uploads"),
    ]

    operations = [
        migrations.AddField(
            model_name="student",
            name="photo",
            field=models.ImageField(blank=True, null=True, upload_to="students/photos/"),
        ),
        migrations.CreateModel(
            name="StudentDocument",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("file", models.FileField(upload_to="students/documents/")),
                ("uploaded_at", models.DateTimeField(auto_now_add=True)),
                ("student", models.ForeignKey(on_delete=models.deletion.CASCADE, related_name="uploaded_documents", to="school.student")),
            ],
        ),
    ]
