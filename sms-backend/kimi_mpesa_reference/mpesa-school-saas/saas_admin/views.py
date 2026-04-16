"""
Admin dashboard API for SaaS platform management.
Provides metrics, controls, and monitoring endpoints.
"""

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import BasePermission
from rest_framework import status
from django.db.models import Sum, Count, Avg, Q
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal

from schools.models import School
from payments.models import Transaction
from billing.models import RevenueLog, SaaSInvoice, Invoice
from fraud_detection.models import Alert
from audit.models import AuditLog


class IsSuperAdmin(BasePermission):
    """Permission for super admin access only."""
    
    def has_permission(self, request, view):
        return (
            request.user.is_authenticated and 
            (request.user.is_superuser or request.user.role == 'SUPERADMIN')
        )


class DashboardOverview(APIView):
    """
    Get dashboard overview metrics.
    
    GET /api/admin/overview/
    """
    permission_classes = [IsSuperAdmin]
    
    def get(self, request):
        # Date range filter
        days = int(request.query_params.get('days', 30))
        since = timezone.now() - timedelta(days=days)
        
        # Revenue metrics
        total_revenue = RevenueLog.objects.aggregate(
            total=Sum('amount')
        )['total'] or Decimal('0')
        
        period_revenue = RevenueLog.objects.filter(
            created_at__gte=since
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0')
        
        # School metrics
        total_schools = School.objects.count()
        active_schools = School.objects.filter(active=True).count()
        new_schools = School.objects.filter(
            created_at__gte=since
        ).count()
        
        # Transaction metrics
        total_transactions = Transaction.objects.count()
        period_transactions = Transaction.objects.filter(
            created_at__gte=since
        )
        period_tx_count = period_transactions.count()
        period_volume = period_transactions.filter(
            status='SUCCESS'
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0')
        
        # Pending alerts
        pending_alerts = Alert.objects.filter(resolved=False)
        critical_alerts = pending_alerts.filter(level='CRITICAL').count()
        warning_alerts = pending_alerts.filter(level='WARNING').count()
        
        # Outstanding invoices
        outstanding = SaaSInvoice.objects.filter(
            status__in=['PENDING', 'OVERDUE']
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0')
        
        # MRR (Monthly Recurring Revenue)
        from billing.engine import BillingEngine
        mrr = BillingEngine.get_mrr()
        
        return Response({
            'revenue': {
                'total': str(total_revenue),
                'period': str(period_revenue),
                'mrr': str(mrr),
                'outstanding': str(outstanding)
            },
            'schools': {
                'total': total_schools,
                'active': active_schools,
                'new_this_period': new_schools,
                'suspended': School.objects.filter(active=False).count()
            },
            'transactions': {
                'total': total_transactions,
                'period_count': period_tx_count,
                'period_volume': str(period_volume),
                'success_rate': self._get_success_rate(since)
            },
            'alerts': {
                'pending': pending_alerts.count(),
                'critical': critical_alerts,
                'warning': warning_alerts
            },
            'period_days': days
        })
    
    def _get_success_rate(self, since):
        """Calculate transaction success rate."""
        period_tx = Transaction.objects.filter(created_at__gte=since)
        total = period_tx.count()
        successful = period_tx.filter(status='SUCCESS').count()
        
        return round((successful / total * 100), 2) if total > 0 else 0


class RevenueChart(APIView):
    """
    Get revenue data for charts.
    
    GET /api/admin/revenue-chart/?days=30
    """
    permission_classes = [IsSuperAdmin]
    
    def get(self, request):
        days = int(request.query_params.get('days', 30))
        
        data = []
        for i in range(days):
            date = timezone.now().date() - timedelta(days=i)
            
            daily_revenue = RevenueLog.objects.filter(
                created_at__date=date
            ).aggregate(total=Sum('amount'))['total'] or Decimal('0')
            
            daily_tx = Transaction.objects.filter(
                created_at__date=date,
                status='SUCCESS'
            ).aggregate(
                count=Count('id'),
                volume=Sum('amount')
            )
            
            data.append({
                'date': date.isoformat(),
                'revenue': str(daily_revenue),
                'transaction_count': daily_tx['count'] or 0,
                'transaction_volume': str(daily_tx['volume'] or Decimal('0'))
            })
        
        return Response(list(reversed(data)))


class SchoolList(APIView):
    """
    List all schools with metrics.
    
    GET /api/admin/schools/
    """
    permission_classes = [IsSuperAdmin]
    
    def get(self, request):
        schools = School.objects.all().select_related('plan')
        
        result = []
        for school in schools:
            # Calculate metrics
            revenue = RevenueLog.objects.filter(
                school=school
            ).aggregate(total=Sum('amount'))['total'] or Decimal('0')
            
            tx_count = Transaction.objects.filter(school=school).count()
            
            student_count = school.students.count() if hasattr(school, 'students') else 0
            
            result.append({
                'id': school.id,
                'name': school.name,
                'code': school.code,
                'active': school.active,
                'subscription_active': school.subscription_active,
                'subscription_expires_at': (
                    school.subscription_expires_at.isoformat() 
                    if school.subscription_expires_at else None
                ),
                'plan': school.plan.name if school.plan else None,
                'revenue': str(revenue),
                'transaction_count': tx_count,
                'student_count': student_count,
                'admin_email': school.admin_email,
                'created_at': school.created_at.isoformat() if hasattr(school, 'created_at') else None
            })
        
        return Response(result)


class ToggleSchool(APIView):
    """
    Toggle school active status.
    
    POST /api/admin/schools/<id>/toggle/
    """
    permission_classes = [IsSuperAdmin]
    
    def post(self, request, school_id):
        try:
            school = School.objects.get(id=school_id)
            school.active = not school.active
            school.save()
            
            action = 'SCHOOL_SUSPENDED' if not school.active else 'SCHOOL_ACTIVATED'
            AuditLog.log_action(request, action, 'SCHOOL', str(school.id), {
                'previous_status': not school.active,
                'new_status': school.active
            })
            
            return Response({
                'success': True,
                'school_id': school.id,
                'active': school.active,
                'message': f"School {'activated' if school.active else 'suspended'}"
            })
            
        except School.DoesNotExist:
            return Response(
                {'error': 'School not found'}, 
                status=status.HTTP_404_NOT_FOUND
            )


class RevenuePerSchool(APIView):
    """
    Get revenue breakdown by school.
    
    GET /api/admin/revenue-per-school/
    """
    permission_classes = [IsSuperAdmin]
    
    def get(self, request):
        days = int(request.query_params.get('days', 30))
        since = timezone.now() - timedelta(days=days)
        
        data = RevenueLog.objects.filter(
            created_at__gte=since
        ).values('school__name').annotate(
            total=Sum('amount'),
            transaction_count=Count('id')
        ).order_by('-total')
        
        return Response(list(data))


class AlertList(APIView):
    """
    List fraud and security alerts.
    
    GET /api/admin/alerts/?resolved=false&level=CRITICAL
    """
    permission_classes = [IsSuperAdmin]
    
    def get(self, request):
        alerts = Alert.objects.select_related('school', 'resolved_by')
        
        # Filters
        resolved = request.query_params.get('resolved')
        if resolved is not None:
            alerts = alerts.filter(resolved=resolved.lower() == 'true')
        
        level = request.query_params.get('level')
        if level:
            alerts = alerts.filter(level=level)
        
        school_id = request.query_params.get('school')
        if school_id:
            alerts = alerts.filter(school_id=school_id)
        
        alerts = alerts.order_by('-created_at')[:100]
        
        result = []
        for alert in alerts:
            result.append({
                'id': alert.id,
                'school': {
                    'id': alert.school.id,
                    'name': alert.school.name
                } if alert.school else None,
                'level': alert.level,
                'type': alert.alert_type,
                'message': alert.message,
                'reference': alert.reference,
                'metadata': alert.metadata,
                'resolved': alert.resolved,
                'resolved_by': (
                    alert.resolved_by.get_full_name() 
                    if alert.resolved_by else None
                ),
                'resolved_at': (
                    alert.resolved_at.isoformat() 
                    if alert.resolved_at else None
                ),
                'resolution_notes': alert.resolution_notes,
                'created_at': alert.created_at.isoformat()
            })
        
        return Response(result)


class ResolveAlert(APIView):
    """
    Resolve an alert.
    
    POST /api/admin/alerts/<id>/resolve/
    {
        "notes": "Investigated and cleared"
    }
    """
    permission_classes = [IsSuperAdmin]
    
    def post(self, request, alert_id):
        try:
            alert = Alert.objects.get(id=alert_id)
            notes = request.data.get('notes', '')
            
            alert.resolve(request.user, notes)
            
            return Response({
                'success': True,
                'message': 'Alert resolved',
                'alert_id': alert.id
            })
            
        except Alert.DoesNotExist:
            return Response(
                {'error': 'Alert not found'}, 
                status=status.HTTP_404_NOT_FOUND
            )


class AuditTrailView(APIView):
    """
    View audit logs.
    
    GET /api/admin/audit/?school=1&entity=TRANSACTION&entity_id=xxx
    """
    permission_classes = [IsSuperAdmin]
    
    def get(self, request):
        logs = AuditLog.objects.select_related('school', 'user')
        
        # Filters
        school_id = request.query_params.get('school')
        if school_id:
            logs = logs.filter(school_id=school_id)
        
        entity = request.query_params.get('entity')
        if entity:
            logs = logs.filter(entity=entity)
        
        entity_id = request.query_params.get('entity_id')
        if entity_id:
            logs = logs.filter(entity_id=entity_id)
        
        action = request.query_params.get('action')
        if action:
            logs = logs.filter(action=action)
        
        user_id = request.query_params.get('user')
        if user_id:
            logs = logs.filter(user_id=user_id)
        
        logs = logs.order_by('-created_at')[:100]
        
        result = []
        for log in logs:
            result.append({
                'id': log.id,
                'timestamp': log.created_at.isoformat(),
                'school': {
                    'id': log.school.id,
                    'name': log.school.name
                } if log.school else None,
                'action': log.action,
                'entity': log.entity,
                'entity_id': log.entity_id,
                'user': {
                    'id': log.user.id,
                    'name': log.user.get_full_name() or log.user.username
                } if log.user else None,
                'metadata': log.metadata,
                'ip_address': log.ip_address,
                'request_path': log.request_path,
                'entry_hash': log.entry_hash[:16] + '...',
                'verified': log.verified
            })
        
        return Response(result)


class ExportAuditCSV(APIView):
    """
    Export audit logs as CSV.
    
    GET /api/admin/audit/export/
    """
    permission_classes = [IsSuperAdmin]
    
    def get(self, request):
        import csv
        from django.http import HttpResponse
        
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="audit_log.csv"'
        
        writer = csv.writer(response)
        writer.writerow([
            'Timestamp', 'School', 'User', 'Action', 'Entity',
            'Entity ID', 'IP Address', 'Request Path', 'Metadata'
        ])
        
        logs = AuditLog.objects.select_related('school', 'user').order_by('-created_at')[:10000]
        
        for log in logs:
            writer.writerow([
                log.created_at.isoformat(),
                log.school.name if log.school else 'N/A',
                log.user.username if log.user else 'System',
                log.action,
                log.entity,
                log.entity_id,
                log.ip_address or '',
                log.request_path or '',
                json.dumps(log.metadata)
            ])
        
        return response


class VerifyAuditChain(APIView):
    """
    Verify audit log integrity for a school.
    
    POST /api/admin/audit/verify/
    {
        "school_id": 1
    }
    """
    permission_classes = [IsSuperAdmin]
    
    def post(self, request):
        school_id = request.data.get('school_id')
        
        if not school_id:
            return Response(
                {'error': 'school_id required'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            school = School.objects.get(id=school_id)
        except School.DoesNotExist:
            return Response(
                {'error': 'School not found'}, 
                status=status.HTTP_404_NOT_FOUND
            )
        
        is_valid, message, broken_entry = AuditLog.verify_chain(school)
        
        return Response({
            'school_id': school_id,
            'school_name': school.name,
            'valid': is_valid,
            'message': message,
            'broken_entry_id': broken_entry.id if broken_entry else None
        })


class SystemHealth(APIView):
    """
    Get system health status.
    
    GET /api/admin/health/
    """
    permission_classes = [IsSuperAdmin]
    
    def get(self, request):
        from django.core.cache import cache
        from django.db import connection
        
        health = {
            'database': self._check_database(),
            'cache': self._check_cache(),
            'celery': self._check_celery(),
            'timestamp': timezone.now().isoformat()
        }
        
        health['overall'] = all([
            health['database']['ok'],
            health['cache']['ok']
        ])
        
        return Response(health)
    
    def _check_database(self):
        """Check database connectivity."""
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                return {'ok': True, 'message': 'Connected'}
        except Exception as e:
            return {'ok': False, 'message': str(e)}
    
    def _check_cache(self):
        """Check cache connectivity."""
        try:
            cache.set('health_check', 'ok', 10)
            value = cache.get('health_check')
            return {'ok': value == 'ok', 'message': 'Connected'}
        except Exception as e:
            return {'ok': False, 'message': str(e)}
    
    def _check_celery(self):
        """Check Celery workers."""
        # This is a basic check - full check would inspect workers
        return {'ok': True, 'message': 'Not implemented'}
