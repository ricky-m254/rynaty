from django.db.models.signals import post_save
from django.dispatch import receiver
from django.db import transaction


@receiver(post_save, sender='school.Enrollment')
def auto_create_alumni_on_completion(sender, instance, created, **kwargs):
    """
    When an Enrollment is marked as Completed, automatically create an
    AlumniProfile for that student (if one does not already exist).
    """
    if instance.status != 'Completed':
        return

    student = instance.student

    def _create():
        from alumni.models import AlumniProfile
        from datetime import date

        already_exists = AlumniProfile.objects.filter(student=student).exists()
        if already_exists:
            return

        graduation_year = date.today().year

        AlumniProfile.objects.create(
            student=student,
            first_name=student.first_name,
            last_name=student.last_name,
            graduation_year=graduation_year,
            admission_number=student.admission_number,
            email=getattr(student, 'email', ''),
            phone=getattr(student, 'phone', ''),
            is_verified=False,
        )

    transaction.on_commit(_create)
