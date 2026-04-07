from django.db import models


class Course(models.Model):
    title = models.CharField(max_length=200)
    subject = models.ForeignKey('school.Subject', null=True, blank=True, on_delete=models.SET_NULL)
    school_class = models.ForeignKey('school.SchoolClass', null=True, blank=True, on_delete=models.SET_NULL)
    teacher = models.ForeignKey('auth.User', on_delete=models.CASCADE, related_name='elearning_courses')
    description = models.TextField(blank=True)
    term = models.ForeignKey('academics.Term', null=True, blank=True, on_delete=models.SET_NULL)
    is_published = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title


class CourseMaterial(models.Model):
    MATERIAL_TYPES = [
        ('PDF', 'PDF Document'),
        ('Video', 'Video Link'),
        ('Presentation', 'Presentation'),
        ('Link', 'External Link'),
        ('Note', 'Text Note'),
    ]
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='materials')
    title = models.CharField(max_length=200)
    material_type = models.CharField(max_length=20, choices=MATERIAL_TYPES, default='PDF')
    file_url = models.CharField(max_length=500, blank=True)
    link_url = models.CharField(max_length=500, blank=True)
    content = models.TextField(blank=True)
    sequence = models.PositiveIntegerField(default=1)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['sequence']

    def __str__(self):
        return f"{self.course.title} — {self.title}"


class OnlineQuiz(models.Model):
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='quizzes')
    title = models.CharField(max_length=200)
    instructions = models.TextField(blank=True)
    time_limit_minutes = models.PositiveIntegerField(null=True, blank=True)
    max_attempts = models.PositiveIntegerField(default=1)
    is_published = models.BooleanField(default=False)
    due_date = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title


class QuizQuestion(models.Model):
    QUESTION_TYPES = [
        ('MCQ', 'Multiple Choice'),
        ('TF', 'True/False'),
        ('SHORT', 'Short Answer'),
    ]
    quiz = models.ForeignKey(OnlineQuiz, on_delete=models.CASCADE, related_name='questions')
    question_text = models.TextField()
    question_type = models.CharField(max_length=10, choices=QUESTION_TYPES, default='MCQ')
    option_a = models.CharField(max_length=300, blank=True)
    option_b = models.CharField(max_length=300, blank=True)
    option_c = models.CharField(max_length=300, blank=True)
    option_d = models.CharField(max_length=300, blank=True)
    correct_answer = models.CharField(max_length=300, blank=True)
    marks = models.PositiveIntegerField(default=1)
    sequence = models.PositiveIntegerField(default=1)

    class Meta:
        ordering = ['sequence']

    def __str__(self):
        return f"Q{self.sequence}: {self.question_text[:60]}"


class QuizAttempt(models.Model):
    STATUS_CHOICES = [
        ('In Progress', 'In Progress'),
        ('Submitted', 'Submitted'),
        ('Graded', 'Graded'),
    ]
    quiz = models.ForeignKey(OnlineQuiz, on_delete=models.CASCADE, related_name='attempts')
    student = models.ForeignKey('school.Student', on_delete=models.CASCADE, related_name='quiz_attempts')
    started_at = models.DateTimeField(auto_now_add=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    score = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    percentage = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    answers = models.JSONField(default=dict, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='In Progress')

    def __str__(self):
        return f"{self.student} — {self.quiz.title}"


class VirtualSession(models.Model):
    PLATFORMS = [
        ('Zoom', 'Zoom'),
        ('Google Meet', 'Google Meet'),
        ('Teams', 'Microsoft Teams'),
        ('Other', 'Other'),
    ]
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='virtual_sessions')
    title = models.CharField(max_length=200)
    session_date = models.DateField()
    start_time = models.TimeField()
    end_time = models.TimeField()
    meeting_link = models.CharField(max_length=500, blank=True)
    platform = models.CharField(max_length=20, choices=PLATFORMS, default='Zoom')
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.course.title} — {self.title} ({self.session_date})"
