"""
Core middleware for multi-tenant school management SaaS.
Handles tenant resolution and request scoping.
"""

from django.http import JsonResponse
from django.core.exceptions import ObjectDoesNotExist


class TenantMiddleware:
    """
    Middleware to resolve tenant (school) from subdomain.
    
    Example:
        school1.yourdomain.com -> School with code='school1'
        school2.yourdomain.com -> School with code='school2'
    """
    
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Skip tenant resolution for admin/superuser paths
        if request.path.startswith('/api/admin/'):
            request.school = None
            request.tenant = None
            return self.get_response(request)
        
        host = request.get_host().split(':')[0]  # Remove port if present
        subdomain = host.split('.')[0]
        
        # Skip for localhost and main domain
        if subdomain in ['localhost', '127', 'www', 'api', '']:
            request.school = None
            request.tenant = None
            return self.get_response(request)
        
        try:
            # Lazy import to avoid circular dependencies
            from schools.models import School
            request.school = School.objects.get(code=subdomain, active=True)
            request.tenant = request.school
            
            # Check subscription for API routes
            if request.path.startswith('/api/') and not request.school.is_subscription_active():
                return JsonResponse(
                    {'error': 'School subscription is inactive or expired'}, 
                    status=403
                )
                
        except ObjectDoesNotExist:
            request.school = None
            request.tenant = None
            
            # Return error for API routes
            if request.path.startswith('/api/'):
                return JsonResponse(
                    {'error': 'School not found or inactive'}, 
                    status=404
                )
        
        return self.get_response(request)


class SecurityHeadersMiddleware:
    """Add security headers to all responses."""
    
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        
        # Security headers
        response['X-Content-Type-Options'] = 'nosniff'
        response['X-Frame-Options'] = 'DENY'
        response['X-XSS-Protection'] = '1; mode=block'
        response['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        response['Permissions-Policy'] = 'geolocation=(), microphone=(), camera=()'
        
        return response


class RequestLoggingMiddleware:
    """Log all API requests for audit trail."""
    
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Process request
        response = self.get_response(request)
        
        # Log API requests
        if request.path.startswith('/api/'):
            # Log asynchronously to avoid blocking
            try:
                from audit.models import AuditLog
                if request.user.is_authenticated:
                    AuditLog.objects.create(
                        school=getattr(request, 'school', None),
                        user=request.user,
                        action='API_REQUEST',
                        entity='REQUEST',
                        entity_id=str(request.path),
                        metadata={
                            'method': request.method,
                            'status_code': response.status_code,
                        },
                        ip_address=self._get_client_ip(request),
                        user_agent=request.META.get('HTTP_USER_AGENT', '')
                    )
            except Exception:
                pass  # Don't fail request if logging fails
        
        return response
    
    def _get_client_ip(self, request):
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0].strip()
        return request.META.get('REMOTE_ADDR')
