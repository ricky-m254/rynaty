from django.utils import timezone
from django.db.models import Sum, Count, Avg, Q
from rest_framework import permissions
from rest_framework.views import APIView
from rest_framework.response import Response
from school.permissions import HasModuleAccess


class ExecutiveDashboardView(APIView):
    permission_classes = [permissions.IsAuthenticated, HasModuleAccess]
    module_key = 'ANALYTICS'

    def get(self, request):
        today = timezone.now().date()
        month_start = today.replace(day=1)
        data = {}

        try:
            from school.models import Student, AttendanceRecord
            data['total_students'] = Student.objects.filter(is_active=True).count()
            present_today = AttendanceRecord.objects.filter(date=today, status='Present').count()
            absent_today = AttendanceRecord.objects.filter(date=today, status='Absent').count()
            total_today = present_today + absent_today
            data['students_present_today'] = present_today
            data['students_absent_today'] = absent_today
            data['student_attendance_rate_today'] = round(present_today / total_today * 100, 1) if total_today > 0 else 0
        except Exception:
            data.update({'total_students': 0, 'students_present_today': 0, 'students_absent_today': 0, 'student_attendance_rate_today': 0})

        try:
            from hr.models import Employee
            data['total_employees'] = Employee.objects.filter(status='Active').count()
        except Exception:
            data['total_employees'] = 0

        try:
            from clockin.models import ClockEvent
            data['staff_clocked_in_today'] = ClockEvent.objects.filter(timestamp__date=today, event_type='IN').count()
            data['staff_late_today'] = ClockEvent.objects.filter(timestamp__date=today, event_type='IN', is_late=True).count()
        except Exception:
            data.update({'staff_clocked_in_today': 0, 'staff_late_today': 0})

        try:
            from school.models import Invoice, Payment
            revenue_this_month = Payment.objects.filter(payment_date__gte=month_start).aggregate(total=Sum('amount_paid'))['total'] or 0
            invoices_unpaid = Invoice.objects.filter(balance_due__gt=0).count()
            total_invoiced = Invoice.objects.filter(issued_date__gte=month_start).aggregate(total=Sum('total_amount'))['total'] or 0
            total_paid = Payment.objects.filter(payment_date__gte=month_start).aggregate(total=Sum('amount_paid'))['total'] or 0
            collection_rate = round(float(total_paid) / float(total_invoiced) * 100, 1) if total_invoiced > 0 else 0
            data['revenue_this_month'] = float(revenue_this_month)
            data['invoices_unpaid'] = invoices_unpaid
            data['collection_rate_percent'] = collection_rate
        except Exception:
            data.update({'revenue_this_month': 0, 'invoices_unpaid': 0, 'collection_rate_percent': 0})

        try:
            from admissions.models import AdmissionDecision
            data['pending_admissions'] = AdmissionDecision.objects.filter(response_status='Pending').count()
        except Exception:
            data['pending_admissions'] = 0

        try:
            from maintenance.models import MaintenanceRequest
            data['open_maintenance'] = MaintenanceRequest.objects.filter(status__in=['Open', 'Assigned', 'In Progress']).count()
        except Exception:
            data['open_maintenance'] = 0

        try:
            from library.models import CirculationTransaction
            data['library_overdue'] = CirculationTransaction.objects.filter(is_overdue=True, return_date__isnull=True).count()
        except Exception:
            data['library_overdue'] = 0

        try:
            from timetable.models import LessonCoverage
            data['uncovered_lessons_today'] = LessonCoverage.objects.filter(date=today, coverage_status='Uncovered').count()
        except Exception:
            data['uncovered_lessons_today'] = 0

        data['last_updated'] = timezone.now().isoformat()
        return Response(data)


class EnrollmentTrendView(APIView):
    permission_classes = [permissions.IsAuthenticated, HasModuleAccess]
    module_key = 'ANALYTICS'

    def get(self, request):
        try:
            from school.models import AcademicYear, Student
            years = AcademicYear.objects.all().order_by('start_year')
            result = []
            for yr in years:
                count = Student.objects.filter(
                    enrollment__academic_year=yr
                ).distinct().count()
                result.append({'year': str(yr), 'total': count, 'year_id': yr.id})
            return Response(result)
        except Exception as e:
            return Response({'error': str(e)}, status=500)


class AttendanceTrendView(APIView):
    permission_classes = [permissions.IsAuthenticated, HasModuleAccess]
    module_key = 'ANALYTICS'

    def get(self, request):
        days = int(request.query_params.get('days', 30))
        try:
            from school.models import AttendanceRecord
            from datetime import timedelta
            today = timezone.now().date()
            result = []
            for i in range(days - 1, -1, -1):
                d = today - timedelta(days=i)
                total = AttendanceRecord.objects.filter(date=d).count()
                present = AttendanceRecord.objects.filter(date=d, status='Present').count()
                rate = round(present / total * 100, 1) if total > 0 else None
                result.append({'date': d.isoformat(), 'rate': rate, 'present': present, 'total': total})
            return Response(result)
        except Exception as e:
            return Response({'error': str(e)}, status=500)


class AtRiskStudentsView(APIView):
    permission_classes = [permissions.IsAuthenticated, HasModuleAccess]
    module_key = 'ANALYTICS'

    def get(self, request):
        try:
            from school.models import Student, AttendanceRecord
            from datetime import timedelta
            today = timezone.now().date()
            cutoff = today - timedelta(days=14)
            students = Student.objects.filter(is_active=True)
            result = []
            for student in students:
                absences = AttendanceRecord.objects.filter(
                    student=student, date__gte=cutoff, status='Absent'
                ).count()
                if absences >= 3:
                    result.append({
                        'student_id': student.id,
                        'name': f"{student.first_name} {student.last_name}",
                        'admission_number': student.admission_number,
                        'risk_reason': 'High Absenteeism',
                        'absences_last_14_days': absences,
                        'latest_average': None,
                    })
            result.sort(key=lambda x: x['absences_last_14_days'], reverse=True)
            return Response(result[:50])
        except Exception as e:
            return Response({'error': str(e)}, status=500)
