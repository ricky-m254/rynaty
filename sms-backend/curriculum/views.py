from rest_framework import viewsets, permissions, status
from rest_framework.views import APIView
from rest_framework.response import Response
from school.permissions import HasModuleAccess
from .models import SchemeOfWork, SchemeTopic, LessonPlan, LearningResource
from .serializers import SchemeOfWorkSerializer, SchemeTopicSerializer, LessonPlanSerializer, LearningResourceSerializer

class SchemeOfWorkViewSet(viewsets.ModelViewSet):
    queryset = SchemeOfWork.objects.all().order_by('-created_at')
    serializer_class = SchemeOfWorkSerializer
    permission_classes = [permissions.IsAuthenticated, HasModuleAccess]
    module_key = "CURRICULUM"
    filterset_fields = ['subject', 'school_class', 'term']

class SchemeTopicViewSet(viewsets.ModelViewSet):
    queryset = SchemeTopic.objects.all().order_by('week_number')
    serializer_class = SchemeTopicSerializer
    permission_classes = [permissions.IsAuthenticated, HasModuleAccess]
    module_key = "CURRICULUM"
    filterset_fields = ['scheme', 'is_covered']

class LessonPlanViewSet(viewsets.ModelViewSet):
    queryset = LessonPlan.objects.all().order_by('-date')
    serializer_class = LessonPlanSerializer
    permission_classes = [permissions.IsAuthenticated, HasModuleAccess]
    module_key = "CURRICULUM"
    filterset_fields = ['topic', 'is_approved']

class LearningResourceViewSet(viewsets.ModelViewSet):
    queryset = LearningResource.objects.all().order_by('-created_at')
    serializer_class = LearningResourceSerializer
    permission_classes = [permissions.IsAuthenticated, HasModuleAccess]
    module_key = "CURRICULUM"
    filterset_fields = ['subject', 'grade_level', 'resource_type']

class CurriculumDashboardView(APIView):
    permission_classes = [permissions.IsAuthenticated, HasModuleAccess]
    module_key = "CURRICULUM"

    def get(self, request):
        total_schemes = SchemeOfWork.objects.count()
        total_topics = SchemeTopic.objects.count()
        covered_topics = SchemeTopic.objects.filter(is_covered=True).count()
        pending_lessons = LessonPlan.objects.filter(is_approved=False).count()
        total_resources = LearningResource.objects.count()
        
        return Response({
            "total_schemes": total_schemes,
            "total_topics": total_topics,
            "covered_topics": covered_topics,
            "coverage_percentage": (covered_topics / total_topics * 100) if total_topics > 0 else 0,
            "pending_lessons": pending_lessons,
            "total_resources": total_resources
        })
