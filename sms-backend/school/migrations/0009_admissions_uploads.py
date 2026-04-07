from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("school", "0008_attendance_behavior"),
    ]

    operations = [
        migrations.AddField(
            model_name="admissionapplication",
            name="student_photo",
            field=models.ImageField(blank=True, null=True, upload_to="admissions/photos/"),
        ),
        migrations.CreateModel(
            name="AdmissionDocument",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("file", models.FileField(upload_to="admissions/documents/")),
                ("uploaded_at", models.DateTimeField(auto_now_add=True)),
                ("application", models.ForeignKey(on_delete=models.deletion.CASCADE, related_name="uploaded_documents", to="school.admissionapplication")),
            ],
        ),
    ]
