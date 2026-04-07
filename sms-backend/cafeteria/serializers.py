from rest_framework import serializers
from .models import MealPlan, WeeklyMenu, StudentMealEnrollment, MealTransaction, CafeteriaWalletTransaction

class MealPlanSerializer(serializers.ModelSerializer):
    class Meta:
        model = MealPlan
        fields = '__all__'

class WeeklyMenuSerializer(serializers.ModelSerializer):
    meal_plan_name = serializers.CharField(source='meal_plan.name', read_only=True)
    class Meta:
        model = WeeklyMenu
        fields = '__all__'

class StudentMealEnrollmentSerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(source='student.__str__', read_only=True)
    meal_plan_name = serializers.CharField(source='meal_plan.name', read_only=True)
    class Meta:
        model = StudentMealEnrollment
        fields = '__all__'

class MealTransactionSerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(source='student.__str__', read_only=True)
    class Meta:
        model = MealTransaction
        fields = '__all__'

class CafeteriaWalletTransactionSerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(source='student.__str__', read_only=True)
    class Meta:
        model = CafeteriaWalletTransaction
        fields = '__all__'
