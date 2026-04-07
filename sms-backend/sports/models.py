from django.db import models

class Club(models.Model):
    CLUB_TYPE_CHOICES = [
        ('Sports', 'Sports'),
        ('Academic', 'Academic'),
        ('Arts', 'Arts'),
        ('Community', 'Community'),
        ('Other', 'Other'),
    ]
    name = models.CharField(max_length=150, unique=True)
    club_type = models.CharField(max_length=20, choices=CLUB_TYPE_CHOICES, default='Sports')
    patron = models.ForeignKey('auth.User', null=True, blank=True, on_delete=models.SET_NULL)
    description = models.TextField(blank=True)
    meeting_day = models.CharField(max_length=20, blank=True)
    meeting_time = models.CharField(max_length=20, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return str(self.name)

class ClubMembership(models.Model):
    ROLE_CHOICES = [
        ('Member', 'Member'),
        ('Captain', 'Captain'),
        ('Vice Captain', 'Vice Captain'),
        ('Secretary', 'Secretary'),
    ]
    club = models.ForeignKey(Club, on_delete=models.CASCADE, related_name='memberships')
    student = models.ForeignKey('school.Student', on_delete=models.CASCADE, related_name='club_memberships')
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='Member')
    joined_date = models.DateField(auto_now_add=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = ('club', 'student')

    def __str__(self) -> str:
        return f"{self.student} - {self.club.name}"

class Tournament(models.Model):
    name = models.CharField(max_length=200)
    club = models.ForeignKey(Club, null=True, blank=True, on_delete=models.SET_NULL)
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    location = models.CharField(max_length=200, blank=True)
    result = models.TextField(blank=True)
    position_achieved = models.CharField(max_length=50, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

class StudentAward(models.Model):
    CATEGORY_CHOICES = [
        ('Academic', 'Academic'),
        ('Sports', 'Sports'),
        ('Arts', 'Arts'),
        ('Leadership', 'Leadership'),
        ('Community', 'Community'),
        ('Other', 'Other'),
    ]
    student = models.ForeignKey('school.Student', on_delete=models.CASCADE, related_name='awards')
    award_name = models.CharField(max_length=200)
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default='Sports')
    awarded_by = models.CharField(max_length=150, blank=True)
    award_date = models.DateField()
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.award_name} - {self.student}"
