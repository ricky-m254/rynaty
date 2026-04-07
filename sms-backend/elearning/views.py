from django.utils import timezone
from rest_framework import viewsets, permissions, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.decorators import action
from school.permissions import HasModuleAccess
from .models import Course, CourseMaterial, OnlineQuiz, QuizQuestion, QuizAttempt, VirtualSession
from .serializers import (
    CourseSerializer, CourseMaterialSerializer, OnlineQuizSerializer,
    QuizQuestionSerializer, QuizAttemptSerializer, VirtualSessionSerializer
)


class CourseViewSet(viewsets.ModelViewSet):
    queryset = Course.objects.all().order_by('-created_at')
    serializer_class = CourseSerializer
    permission_classes = [permissions.IsAuthenticated, HasModuleAccess]
    module_key = 'ELEARNING'
    filterset_fields = ['teacher', 'school_class', 'term', 'is_published']

    def perform_create(self, serializer):
        serializer.save(teacher=self.request.user)


class CourseMaterialViewSet(viewsets.ModelViewSet):
    queryset = CourseMaterial.objects.all().order_by('sequence')
    serializer_class = CourseMaterialSerializer
    permission_classes = [permissions.IsAuthenticated, HasModuleAccess]
    module_key = 'ELEARNING'
    filterset_fields = ['course', 'material_type', 'is_active']


class OnlineQuizViewSet(viewsets.ModelViewSet):
    queryset = OnlineQuiz.objects.all().order_by('-created_at')
    serializer_class = OnlineQuizSerializer
    permission_classes = [permissions.IsAuthenticated, HasModuleAccess]
    module_key = 'ELEARNING'
    filterset_fields = ['course', 'is_published']


class QuizQuestionViewSet(viewsets.ModelViewSet):
    queryset = QuizQuestion.objects.all().order_by('sequence')
    serializer_class = QuizQuestionSerializer
    permission_classes = [permissions.IsAuthenticated, HasModuleAccess]
    module_key = 'ELEARNING'
    filterset_fields = ['quiz']


class QuizAttemptViewSet(viewsets.ModelViewSet):
    queryset = QuizAttempt.objects.all().order_by('-started_at')
    serializer_class = QuizAttemptSerializer
    permission_classes = [permissions.IsAuthenticated, HasModuleAccess]
    module_key = 'ELEARNING'
    filterset_fields = ['quiz', 'student', 'status']

    @action(detail=True, methods=['post'])
    def submit(self, request, pk=None):
        attempt = self.get_object()
        answers = request.data.get('answers', {})
        attempt.answers = answers
        attempt.submitted_at = timezone.now()
        attempt.status = 'Submitted'

        total_marks = 0
        earned_marks = 0
        questions = attempt.quiz.questions.all()
        for q in questions:
            total_marks += q.marks
            given = str(answers.get(str(q.id), '')).strip().upper()
            correct = str(q.correct_answer).strip().upper()
            if q.question_type in ('MCQ', 'TF') and given == correct:
                earned_marks += q.marks

        attempt.score = earned_marks
        attempt.percentage = round((earned_marks / total_marks * 100), 2) if total_marks > 0 else 0
        attempt.status = 'Graded'
        attempt.save()
        return Response({'score': attempt.score, 'percentage': attempt.percentage}, status=status.HTTP_200_OK)


class VirtualSessionViewSet(viewsets.ModelViewSet):
    queryset = VirtualSession.objects.all().order_by('session_date', 'start_time')
    serializer_class = VirtualSessionSerializer
    permission_classes = [permissions.IsAuthenticated, HasModuleAccess]
    module_key = 'ELEARNING'
    filterset_fields = ['course']


class ELearningDashboardView(APIView):
    permission_classes = [permissions.IsAuthenticated, HasModuleAccess]
    module_key = 'ELEARNING'

    def get(self, request):
        today = timezone.now().date()
        user = request.user
        my_courses = Course.objects.filter(teacher=user)
        upcoming_sessions = VirtualSession.objects.filter(session_date__gte=today).order_by('session_date', 'start_time')[:5]
        pending_quizzes = OnlineQuiz.objects.filter(is_published=True, due_date__gte=timezone.now()).order_by('due_date')[:5]
        recent_materials = CourseMaterial.objects.filter(is_active=True).order_by('-created_at')[:5]

        return Response({
            'my_courses_count': my_courses.count(),
            'published_courses': my_courses.filter(is_published=True).count(),
            'total_materials': CourseMaterial.objects.count(),
            'total_quizzes': OnlineQuiz.objects.count(),
            'upcoming_sessions': [
                {
                    'id': s.id,
                    'title': s.title,
                    'course': s.course.title,
                    'session_date': s.session_date,
                    'start_time': s.start_time,
                    'platform': s.platform,
                    'meeting_link': s.meeting_link,
                }
                for s in upcoming_sessions
            ],
            'pending_quizzes': [
                {
                    'id': q.id,
                    'title': q.title,
                    'course': q.course.title,
                    'due_date': q.due_date,
                }
                for q in pending_quizzes
            ],
            'recent_materials': [
                {
                    'id': m.id,
                    'title': m.title,
                    'course': m.course.title,
                    'material_type': m.material_type,
                }
                for m in recent_materials
            ],
        })
