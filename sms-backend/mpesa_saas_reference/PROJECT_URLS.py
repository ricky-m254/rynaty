"""
Example main urls.py for your Django project.

Add these URL patterns to your project's main urls.py file.
"""

from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

# DRF Spectacular for API documentation
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView
)

urlpatterns = [
    # Django Admin
    path('admin/', admin.site.urls),
    
    # API Documentation
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('api/redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),
    
    # Authentication (if using simplejwt)
    path('api/auth/', include('rest_framework_simplejwt.urls')),
    
    # Your existing apps
    # path('api/schools/', include('schools.urls')),
    # path('api/users/', include('users.urls')),
    
    # Payment integration
    path('api/payments/', include('payments.urls')),
    
    # SaaS Admin Dashboard API
    path('api/admin/', include('saas_admin.urls')),
]

# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    
    # Add debug toolbar if installed
    # import debug_toolbar
    # urlpatterns = [
    #     path('__debug__/', include(debug_toolbar.urls)),
    # ] + urlpatterns
