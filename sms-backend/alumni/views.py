from rest_framework import viewsets, permissions, status
from rest_framework.views import APIView
from rest_framework.response import Response
from django.db.models import Count
from school.permissions import HasModuleAccess
from .models import AlumniProfile, AlumniEvent, AlumniEventAttendee, AlumniMentorship, AlumniDonation
from .serializers import AlumniProfileSerializer, AlumniEventSerializer, AlumniEventAttendeeSerializer, AlumniMentorshipSerializer, AlumniDonationSerializer
from django.db.models import Sum

class AlumniProfileViewSet(viewsets.ModelViewSet):
    queryset = AlumniProfile.objects.all().order_by('-graduation_year')
    serializer_class = AlumniProfileSerializer
    permission_classes = [permissions.IsAuthenticated, HasModuleAccess]
    module_key = "ALUMNI"
    filterset_fields = ['graduation_year', 'is_verified', 'country']

class AlumniEventViewSet(viewsets.ModelViewSet):
    queryset = AlumniEvent.objects.all().order_by('-event_date')
    serializer_class = AlumniEventSerializer
    permission_classes = [permissions.IsAuthenticated, HasModuleAccess]
    module_key = "ALUMNI"
    filterset_fields = ['event_date']

class AlumniEventAttendeeViewSet(viewsets.ModelViewSet):
    queryset = AlumniEventAttendee.objects.all()
    serializer_class = AlumniEventAttendeeSerializer
    permission_classes = [permissions.IsAuthenticated, HasModuleAccess]
    module_key = "ALUMNI"
    filterset_fields = ['event', 'alumni']

class AlumniMentorshipViewSet(viewsets.ModelViewSet):
    queryset = AlumniMentorship.objects.all().select_related('mentor').order_by('-created_at')
    serializer_class = AlumniMentorshipSerializer
    permission_classes = [permissions.IsAuthenticated, HasModuleAccess]
    module_key = "ALUMNI"
    filterset_fields = ['status', 'mentor', 'mentee_type']


class AlumniDonationViewSet(viewsets.ModelViewSet):
    queryset = AlumniDonation.objects.all().select_related('alumni').order_by('-donation_date')
    serializer_class = AlumniDonationSerializer
    permission_classes = [permissions.IsAuthenticated, HasModuleAccess]
    module_key = "ALUMNI"
    filterset_fields = ['status', 'alumni', 'payment_method']


class AlumniDashboardView(APIView):
    permission_classes = [permissions.IsAuthenticated, HasModuleAccess]
    module_key = "ALUMNI"

    def get(self, request):
        total_alumni = AlumniProfile.objects.count()
        by_year = AlumniProfile.objects.values('graduation_year').annotate(count=Count('id')).order_by('-graduation_year')
        by_country = AlumniProfile.objects.values('country').annotate(count=Count('id')).order_by('-count')
        
        return Response({
            "total_alumni": total_alumni,
            "graduation_year_breakdown": by_year,
            "country_breakdown": by_country
        }, status=status.HTTP_200_OK)
