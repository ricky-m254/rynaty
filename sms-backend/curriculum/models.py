from django.db import models

class SchemeOfWork(models.Model):
    subject = models.ForeignKey('school.Subject', on_delete=models.CASCADE, related_name='schemes')
    school_class = models.ForeignKey('school.SchoolClass', on_delete=models.CASCADE)
    term = models.ForeignKey('school.Term', on_delete=models.CASCADE)
    title = models.CharField(max_length=200)
    objectives = models.TextField(blank=True)
    created_by = models.ForeignKey('auth.User', null=True, blank=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('subject', 'school_class', 'term')

    def __str__(self):
        return f"{self.title} - {self.subject.name}"

class SchemeTopic(models.Model):
    scheme = models.ForeignKey(SchemeOfWork, on_delete=models.CASCADE, related_name='topics')
    week_number = models.PositiveIntegerField()
    topic = models.CharField(max_length=300)
    sub_topics = models.TextField(blank=True)
    learning_outcomes = models.TextField(blank=True)
    teaching_methods = models.TextField(blank=True)
    resources = models.TextField(blank=True)
    assessment_type = models.CharField(max_length=100, blank=True)
    is_covered = models.BooleanField(default=False)
    covered_date = models.DateField(null=True, blank=True)

    def __str__(self):
        return f"Week {self.week_number}: {self.topic}"

class LessonPlan(models.Model):
    topic = models.ForeignKey(SchemeTopic, on_delete=models.CASCADE, related_name='lesson_plans')
    date = models.DateField()
    lesson_objectives = models.TextField()
    introduction = models.TextField(blank=True)
    presentation = models.TextField(blank=True)
    conclusion = models.TextField(blank=True)
    assessment_activity = models.TextField(blank=True)
    homework = models.TextField(blank=True)
    teacher_reflection = models.TextField(blank=True)
    is_approved = models.BooleanField(default=False)
    approved_by = models.ForeignKey('auth.User', null=True, blank=True, on_delete=models.SET_NULL, related_name='approved_lesson_plans')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Lesson Plan - {self.topic.topic} ({self.date})"

class LearningResource(models.Model):
    RESOURCE_TYPE_CHOICES = [
        ('Document', 'Document/PDF'),
        ('Video', 'Video Link'),
        ('Image', 'Image'),
        ('Audio', 'Audio'),
        ('Link', 'External Link'),
        ('Other', 'Other'),
    ]
    title = models.CharField(max_length=200)
    resource_type = models.CharField(max_length=20, choices=RESOURCE_TYPE_CHOICES, default='Document')
    subject = models.ForeignKey('school.Subject', on_delete=models.CASCADE)
    grade_level = models.ForeignKey('school.GradeLevel', on_delete=models.SET_NULL, null=True, blank=True)
    file = models.FileField(upload_to='curriculum/resources/', null=True, blank=True)
    external_url = models.CharField(max_length=500, blank=True)
    description = models.TextField(blank=True)
    uploaded_by = models.ForeignKey('auth.User', null=True, blank=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return str(self.title)
