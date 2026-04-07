from django.db import models


class AcademicYear(models.Model):
    """
    Unmanaged wrapper for school.AcademicYear (pilot migration).
    """
    name = models.CharField(max_length=50)
    start_date = models.DateField()
    end_date = models.DateField()
    is_active = models.BooleanField(default=True)
    is_current = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        managed = False
        db_table = "school_academicyear"

    def __str__(self):
        return self.name


class Term(models.Model):
    """
    Unmanaged wrapper for school.Term (pilot migration).
    """
    academic_year = models.ForeignKey(AcademicYear, on_delete=models.DO_NOTHING)
    name = models.CharField(max_length=50)
    start_date = models.DateField()
    end_date = models.DateField()
    billing_date = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    is_current = models.BooleanField(default=False)

    class Meta:
        managed = False
        db_table = "school_term"

    def __str__(self):
        return f"{self.academic_year.name} - {self.name}"


class SchoolClass(models.Model):
    """
    Unmanaged wrapper for school.SchoolClass (pilot migration).
    """
    name = models.CharField(max_length=50)
    stream = models.CharField(max_length=50, blank=True)
    academic_year = models.ForeignKey(AcademicYear, on_delete=models.DO_NOTHING)
    grade_level = models.ForeignKey("GradeLevel", on_delete=models.DO_NOTHING, null=True, blank=True)
    section_name = models.CharField(max_length=50, blank=True)
    class_teacher = models.ForeignKey("auth.User", on_delete=models.DO_NOTHING, null=True, blank=True)
    room = models.CharField(max_length=100, blank=True)
    capacity = models.PositiveIntegerField(default=40)
    is_active = models.BooleanField(default=True)

    class Meta:
        managed = False
        db_table = "school_schoolclass"

    def __str__(self):
        return f"{self.name} - {self.stream}"

    @property
    def display_name(self):
        if self.grade_level and self.section_name:
            return f"{self.grade_level.name} {self.section_name}".strip()
        if self.stream:
            return f"{self.name} {self.stream}".strip()
        return self.name


class GradeLevel(models.Model):
    name = models.CharField(max_length=50, unique=True)
    order = models.PositiveIntegerField(default=1)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        managed = False
        db_table = "school_gradelevel"
        ordering = ["order", "name"]

    def __str__(self):
        return self.name
