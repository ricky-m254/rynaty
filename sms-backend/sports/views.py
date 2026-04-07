from rest_framework import viewsets, permissions, status
from rest_framework.views import APIView
from rest_framework.response import Response
from school.permissions import HasModuleAccess
from .models import Club, ClubMembership, Tournament, StudentAward
from .serializers import ClubSerializer, ClubMembershipSerializer, TournamentSerializer, StudentAwardSerializer

class ClubViewSet(viewsets.ModelViewSet):
    queryset = Club.objects.all().order_by('name')
    serializer_class = ClubSerializer
    permission_classes = [permissions.IsAuthenticated, HasModuleAccess]
    module_key = "SPORTS"
    filterset_fields = ['club_type', 'is_active']

class ClubMembershipViewSet(viewsets.ModelViewSet):
    queryset = ClubMembership.objects.all().order_by('-joined_date')
    serializer_class = ClubMembershipSerializer
    permission_classes = [permissions.IsAuthenticated, HasModuleAccess]
    module_key = "SPORTS"
    filterset_fields = ['club', 'is_active']

class TournamentViewSet(viewsets.ModelViewSet):
    queryset = Tournament.objects.all().order_by('-start_date')
    serializer_class = TournamentSerializer
    permission_classes = [permissions.IsAuthenticated, HasModuleAccess]
    module_key = "SPORTS"
    filterset_fields = ['club']

class StudentAwardViewSet(viewsets.ModelViewSet):
    queryset = StudentAward.objects.all().order_by('-award_date')
    serializer_class = StudentAwardSerializer
    permission_classes = [permissions.IsAuthenticated, HasModuleAccess]
    module_key = "SPORTS"
    filterset_fields = ['category', 'student']

class SportsDashboardView(APIView):
    permission_classes = [permissions.IsAuthenticated, HasModuleAccess]
    module_key = "SPORTS"

    def get(self, request):
        active_clubs = Club.objects.filter(is_active=True).count()
        total_members = ClubMembership.objects.filter(is_active=True).count()
        import datetime
        upcoming_tournaments = Tournament.objects.filter(start_date__gte=datetime.date.today()).count()
        recent_awards = StudentAward.objects.all().order_by('-award_date')[:10]
        
        return Response({
            "active_clubs": active_clubs,
            "total_members": total_members,
            "upcoming_tournaments": upcoming_tournaments,
            "recent_awards": StudentAwardSerializer(recent_awards, many=True).data
        })
