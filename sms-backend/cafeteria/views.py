from rest_framework import viewsets, permissions, status
from rest_framework.views import APIView
from rest_framework.response import Response
from school.permissions import HasModuleAccess
from .models import MealPlan, WeeklyMenu, StudentMealEnrollment, MealTransaction, CafeteriaWalletTransaction
from .serializers import MealPlanSerializer, WeeklyMenuSerializer, StudentMealEnrollmentSerializer, MealTransactionSerializer, CafeteriaWalletTransactionSerializer
import datetime

class MealPlanViewSet(viewsets.ModelViewSet):
    queryset = MealPlan.objects.all().order_by('name')
    serializer_class = MealPlanSerializer
    permission_classes = [permissions.IsAuthenticated, HasModuleAccess]
    module_key = "CAFETERIA"
    filterset_fields = ['is_active']

class WeeklyMenuViewSet(viewsets.ModelViewSet):
    queryset = WeeklyMenu.objects.all().order_by('-week_start')
    serializer_class = WeeklyMenuSerializer
    permission_classes = [permissions.IsAuthenticated, HasModuleAccess]
    module_key = "CAFETERIA"
    filterset_fields = ['meal_plan', 'week_start']

class StudentMealEnrollmentViewSet(viewsets.ModelViewSet):
    queryset = StudentMealEnrollment.objects.all().order_by('-created_at')
    serializer_class = StudentMealEnrollmentSerializer
    permission_classes = [permissions.IsAuthenticated, HasModuleAccess]
    module_key = "CAFETERIA"
    filterset_fields = ['meal_plan', 'is_active', 'term']

class MealTransactionViewSet(viewsets.ModelViewSet):
    queryset = MealTransaction.objects.all().order_by('-date', '-created_at')
    serializer_class = MealTransactionSerializer
    permission_classes = [permissions.IsAuthenticated, HasModuleAccess]
    module_key = "CAFETERIA"
    filterset_fields = ['student', 'date', 'meal_type']

class CafeteriaWalletTransactionViewSet(viewsets.ModelViewSet):
    queryset = CafeteriaWalletTransaction.objects.all().order_by('-created_at')
    serializer_class = CafeteriaWalletTransactionSerializer
    permission_classes = [permissions.IsAuthenticated, HasModuleAccess]
    module_key = "CAFETERIA"
    filterset_fields = ['student', 'transaction_type']

class CafeteriaDashboardView(APIView):
    permission_classes = [permissions.IsAuthenticated, HasModuleAccess]
    module_key = "CAFETERIA"

    def get(self, request):
        today = datetime.date.today()
        today_meal_count = MealTransaction.objects.filter(date=today, served=True).count()
        enrolled_students = StudentMealEnrollment.objects.filter(is_active=True).count()
        
        # Get this week's menu (Monday)
        monday = today - datetime.timedelta(days=today.weekday())
        this_week_menu = WeeklyMenu.objects.filter(week_start=monday)
        
        return Response({
            "today_meal_count": today_meal_count,
            "enrolled_students": enrolled_students,
            "this_week_menu_count": this_week_menu.count()
        })
