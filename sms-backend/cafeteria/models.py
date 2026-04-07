from django.db import models

class MealPlan(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    price_per_day = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    is_active = models.BooleanField(default=True)

    def __str__(self) -> str:
        return str(self.name)

class WeeklyMenu(models.Model):
    week_start = models.DateField()
    meal_plan = models.ForeignKey(MealPlan, on_delete=models.CASCADE, related_name='weekly_menus')
    monday_breakfast = models.TextField(blank=True)
    monday_lunch = models.TextField(blank=True)
    monday_supper = models.TextField(blank=True)
    tuesday_breakfast = models.TextField(blank=True)
    tuesday_lunch = models.TextField(blank=True)
    tuesday_supper = models.TextField(blank=True)
    wednesday_breakfast = models.TextField(blank=True)
    wednesday_lunch = models.TextField(blank=True)
    wednesday_supper = models.TextField(blank=True)
    thursday_breakfast = models.TextField(blank=True)
    thursday_lunch = models.TextField(blank=True)
    thursday_supper = models.TextField(blank=True)
    friday_breakfast = models.TextField(blank=True)
    friday_lunch = models.TextField(blank=True)
    friday_supper = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('week_start', 'meal_plan')

    def __str__(self):
        return f"{self.meal_plan.name} - Week of {self.week_start}"

class StudentMealEnrollment(models.Model):
    student = models.ForeignKey('school.Student', on_delete=models.CASCADE, related_name='meal_enrollments')
    meal_plan = models.ForeignKey(MealPlan, on_delete=models.CASCADE)
    term = models.ForeignKey('academics.Term', null=True, blank=True, on_delete=models.SET_NULL)
    dietary_notes = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.student} - {self.meal_plan.name}"

class MealTransaction(models.Model):
    MEAL_TYPE_CHOICES = [
        ('Breakfast', 'Breakfast'),
        ('Lunch', 'Lunch'),
        ('Supper', 'Supper'),
    ]
    student = models.ForeignKey('school.Student', on_delete=models.CASCADE, related_name='meal_transactions')
    date = models.DateField()
    meal_type = models.CharField(max_length=20, choices=MEAL_TYPE_CHOICES, default='Lunch')
    served = models.BooleanField(default=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('student', 'date', 'meal_type')

    def __str__(self):
        return f"{self.student} - {self.date} - {self.meal_type}"

class CafeteriaWalletTransaction(models.Model):
    TRANSACTION_TYPE_CHOICES = [
        ('Credit', 'Credit'),
        ('Debit', 'Debit'),
    ]
    student = models.ForeignKey('school.Student', on_delete=models.CASCADE, related_name='wallet_transactions')
    transaction_type = models.CharField(max_length=20, choices=TRANSACTION_TYPE_CHOICES)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    description = models.CharField(max_length=200, blank=True)
    balance_after = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.student} - {self.transaction_type} - {self.amount}"
