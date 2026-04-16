from decimal import Decimal

from django.db.models import Sum
from rest_framework import viewsets, permissions, status
from rest_framework.views import APIView
from rest_framework.response import Response
from school.permissions import HasModuleAccess
from .models import MealPlan, WeeklyMenu, StudentMealEnrollment, MealTransaction, CafeteriaWalletTransaction
from .serializers import MealPlanSerializer, WeeklyMenuSerializer, StudentMealEnrollmentSerializer, MealTransactionSerializer, CafeteriaWalletTransactionSerializer
import datetime


def _get_student_balance(student):
    latest = (
        CafeteriaWalletTransaction.objects
        .filter(student=student)
        .order_by('-created_at', '-id')
        .first()
    )
    return latest.balance_after if latest else Decimal('0.00')


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

    def perform_create(self, serializer):
        instance = serializer.save()
        student = instance.student
        if not instance.served:
            return
        enrollment = (
            StudentMealEnrollment.objects
            .filter(student=student, is_active=True)
            .select_related('meal_plan')
            .first()
        )
        if enrollment and enrollment.meal_plan and enrollment.meal_plan.price_per_day:
            meal_cost = Decimal(str(enrollment.meal_plan.price_per_day)) / 3
            if meal_cost > 0:
                current_balance = _get_student_balance(student)
                new_balance = current_balance - meal_cost
                CafeteriaWalletTransaction.objects.create(
                    student=student,
                    transaction_type='Debit',
                    amount=meal_cost,
                    description=f"{instance.meal_type} on {instance.date}",
                    balance_after=new_balance,
                )


class CafeteriaWalletTransactionViewSet(viewsets.ModelViewSet):
    queryset = CafeteriaWalletTransaction.objects.all().order_by('-created_at')
    serializer_class = CafeteriaWalletTransactionSerializer
    permission_classes = [permissions.IsAuthenticated, HasModuleAccess]
    module_key = "CAFETERIA"
    filterset_fields = ['student', 'transaction_type']

    def perform_create(self, serializer):
        student = serializer.validated_data['student']
        current_balance = _get_student_balance(student)
        transaction_type = serializer.validated_data['transaction_type']
        amount = Decimal(str(serializer.validated_data['amount']))

        if transaction_type == 'Credit':
            new_balance = current_balance + amount
        else:
            new_balance = current_balance - amount

        serializer.save(balance_after=new_balance)


class CafeteriaDashboardView(APIView):
    permission_classes = [permissions.IsAuthenticated, HasModuleAccess]
    module_key = "CAFETERIA"

    def get(self, request):
        today = datetime.date.today()
        today_meal_count = MealTransaction.objects.filter(date=today, served=True).count()
        enrolled_students = StudentMealEnrollment.objects.filter(is_active=True).count()

        monday = today - datetime.timedelta(days=today.weekday())
        this_week_menu = WeeklyMenu.objects.filter(week_start=monday)

        low_balance_count = 0
        for enrollment in StudentMealEnrollment.objects.filter(is_active=True).select_related('student'):
            balance = _get_student_balance(enrollment.student)
            if balance < 200:
                low_balance_count += 1

        return Response({
            "today_meal_count": today_meal_count,
            "enrolled_students": enrolled_students,
            "this_week_menu_count": this_week_menu.count(),
            "low_balance_count": low_balance_count,
        })


class StudentAccountsView(APIView):
    permission_classes = [permissions.IsAuthenticated, HasModuleAccess]
    module_key = "CAFETERIA"

    def get(self, request):
        from school.models import Enrollment

        enrollments = (
            StudentMealEnrollment.objects
            .filter(is_active=True)
            .select_related('student', 'meal_plan')
            .order_by('student__first_name', 'student__last_name')
        )

        seen_students = set()
        result = []

        for enrollment in enrollments:
            student = enrollment.student
            if student.id in seen_students:
                continue
            seen_students.add(student.id)

            latest_wallet = (
                CafeteriaWalletTransaction.objects
                .filter(student=student)
                .order_by('-created_at', '-id')
                .first()
            )
            current_balance = float(latest_wallet.balance_after) if latest_wallet else 0.0
            last_tx_date = (
                latest_wallet.created_at.strftime('%Y-%m-%d') if latest_wallet else None
            )

            total_spent = (
                CafeteriaWalletTransaction.objects
                .filter(student=student, transaction_type='Debit')
                .aggregate(t=Sum('amount'))['t'] or Decimal('0.00')
            )

            school_enrollment = (
                Enrollment.objects
                .filter(student=student, is_active=True)
                .select_related('school_class')
                .first()
            )
            grade = (
                school_enrollment.school_class.name
                if school_enrollment and school_enrollment.school_class
                else 'N/A'
            )

            if current_balance <= 0:
                acct_status = 'Suspended'
            elif current_balance < 200:
                acct_status = 'Low Balance'
            else:
                acct_status = 'Active'

            result.append({
                'id': student.id,
                'studentName': f"{student.first_name} {student.last_name}".strip(),
                'admissionNo': student.admission_number or '',
                'grade': grade,
                'balance': current_balance,
                'totalSpent': float(total_spent),
                'lastTransaction': last_tx_date,
                'mealPlan': enrollment.meal_plan.name if enrollment.meal_plan else 'N/A',
                'status': acct_status,
            })

        return Response(result)


class CafeteriaPreOrdersView(APIView):
    permission_classes = [permissions.IsAuthenticated, HasModuleAccess]
    module_key = "CAFETERIA"

    def get(self, request):
        from django.utils import timezone
        from school.models import Enrollment
        today = timezone.now().date()
        start = today - datetime.timedelta(days=14)
        end = today + datetime.timedelta(days=7)

        transactions = (
            MealTransaction.objects
            .filter(date__range=(start, end))
            .select_related('student')
            .order_by('-date', '-id')[:200]
        )

        student_ids = list({t.student_id for t in transactions})
        grade_map = {}
        for enr in (
            Enrollment.objects
            .filter(student_id__in=student_ids, is_active=True)
            .select_related('school_class')
        ):
            grade_map[enr.student_id] = getattr(enr.school_class, 'name', '')

        results = []
        for t in transactions:
            s = t.student
            name = f"{s.first_name} {s.last_name}".strip() or s.admission_number
            status_val = "Confirmed" if t.served else "Pending"
            results.append({
                'id': t.id,
                'orderId': f'ORD-{t.date.year}-{t.id:05d}',
                'studentName': name,
                'grade': grade_map.get(s.id, ''),
                'mealDate': str(t.date),
                'mealType': t.meal_type,
                'mealItem': t.meal_type,
                'orderedBy': 'School',
                'placedAt': t.created_at.strftime('%Y-%m-%d %H:%M'),
                'status': status_val,
            })

        return Response(results)

    def patch(self, request, pk):
        action = request.data.get('status')
        try:
            t = MealTransaction.objects.get(id=pk)
            if action == 'Confirmed':
                t.served = True
                t.save(update_fields=['served'])
            elif action == 'Cancelled':
                t.served = False
                t.save(update_fields=['served'])
            return Response({'status': 'ok', 'id': pk})
        except MealTransaction.DoesNotExist:
            return Response({'error': 'Not found'}, status=status.HTTP_404_NOT_FOUND)


class WalletBalanceView(APIView):
    permission_classes = [permissions.IsAuthenticated, HasModuleAccess]
    module_key = "CAFETERIA"

    def get(self, request):
        from school.models import Student as StudentModel

        student_id = request.query_params.get('student')
        if not student_id:
            return Response({'error': 'student parameter required'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            student = StudentModel.objects.get(id=student_id)
        except StudentModel.DoesNotExist:
            return Response({'error': 'Student not found'}, status=status.HTTP_404_NOT_FOUND)

        current_balance = _get_student_balance(student)
        total_credits = (
            CafeteriaWalletTransaction.objects
            .filter(student=student, transaction_type='Credit')
            .aggregate(t=Sum('amount'))['t'] or Decimal('0.00')
        )
        total_debits = (
            CafeteriaWalletTransaction.objects
            .filter(student=student, transaction_type='Debit')
            .aggregate(t=Sum('amount'))['t'] or Decimal('0.00')
        )
        return Response({
            'student_id': student.id,
            'current_balance': float(current_balance),
            'total_topped_up': float(total_credits),
            'total_spent': float(total_debits),
        })
