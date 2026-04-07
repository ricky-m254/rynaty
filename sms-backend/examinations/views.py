from django.utils import timezone
from rest_framework import viewsets, permissions, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from django.db.models import Avg, Max, Count
from school.permissions import HasModuleAccess
from .models import (
    ExamSession, ExamPaper, ExamSeatAllocation, ExamResult,
    ExamGradeBoundary, ExamPaperUpload, ExamSetterAssignment
)
from .serializers import (
    ExamSessionSerializer, ExamPaperSerializer, ExamSeatAllocationSerializer,
    ExamResultSerializer, ExamGradeBoundarySerializer,
    ExamPaperUploadSerializer, ExamSetterAssignmentSerializer
)

class ExamSessionViewSet(viewsets.ModelViewSet):
    queryset = ExamSession.objects.all().order_by('-created_at')
    serializer_class = ExamSessionSerializer
    permission_classes = [permissions.IsAuthenticated, HasModuleAccess]
    module_key = "EXAMINATIONS"

class ExamPaperViewSet(viewsets.ModelViewSet):
    queryset = ExamPaper.objects.select_related('session', 'subject', 'school_class', 'invigilator').order_by('-exam_date')
    serializer_class = ExamPaperSerializer
    permission_classes = [permissions.IsAuthenticated, HasModuleAccess]
    module_key = "EXAMINATIONS"

    def get_queryset(self):
        qs = super().get_queryset()
        session = self.request.query_params.get('session')
        if session:
            qs = qs.filter(session_id=session)
        return qs

class ExamSeatAllocationViewSet(viewsets.ModelViewSet):
    queryset = ExamSeatAllocation.objects.select_related('student', 'paper').all()
    serializer_class = ExamSeatAllocationSerializer
    permission_classes = [permissions.IsAuthenticated, HasModuleAccess]
    module_key = "EXAMINATIONS"

    def get_queryset(self):
        qs = super().get_queryset()
        paper = self.request.query_params.get('paper')
        if paper:
            qs = qs.filter(paper_id=paper)
        return qs

class ExamResultViewSet(viewsets.ModelViewSet):
    queryset = ExamResult.objects.select_related('student', 'paper__subject', 'paper__school_class').all()
    serializer_class = ExamResultSerializer
    permission_classes = [permissions.IsAuthenticated, HasModuleAccess]
    module_key = "EXAMINATIONS"

    def get_queryset(self):
        qs = super().get_queryset()
        paper = self.request.query_params.get('paper')
        session = self.request.query_params.get('session')
        student = self.request.query_params.get('student')
        if paper:
            qs = qs.filter(paper_id=paper)
        if session:
            qs = qs.filter(paper__session_id=session)
        if student:
            qs = qs.filter(student_id=student)
        return qs

    @action(detail=False, methods=['post'], url_path='calculate-positions')
    def calculate_positions(self, request):
        paper_id = request.data.get('paper_id')
        if not paper_id:
            return Response({"error": "paper_id is required"}, status=status.HTTP_400_BAD_REQUEST)
        results = ExamResult.objects.filter(paper_id=paper_id).order_by('-marks_obtained')
        for i, res in enumerate(results):
            res.position = i + 1
            res.save()
        return Response({"message": f"Positions calculated for {results.count()} results"})

class ExamGradeBoundaryViewSet(viewsets.ModelViewSet):
    queryset = ExamGradeBoundary.objects.all()
    serializer_class = ExamGradeBoundarySerializer
    permission_classes = [permissions.IsAuthenticated, HasModuleAccess]
    module_key = "EXAMINATIONS"

    def get_queryset(self):
        qs = super().get_queryset()
        session = self.request.query_params.get('session')
        if session:
            qs = qs.filter(session_id=session)
        return qs

class ExamPaperUploadViewSet(viewsets.ModelViewSet):
    queryset = ExamPaperUpload.objects.select_related(
        'session', 'subject', 'school_class', 'uploaded_by', 'reviewed_by'
    ).order_by('-created_at')
    serializer_class = ExamPaperUploadSerializer
    permission_classes = [permissions.IsAuthenticated, HasModuleAccess]
    module_key = "EXAMINATIONS"
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get_queryset(self):
        qs = super().get_queryset()
        session = self.request.query_params.get('session')
        status_filter = self.request.query_params.get('status')
        if session:
            qs = qs.filter(session_id=session)
        if status_filter:
            qs = qs.filter(status=status_filter)
        return qs

    def perform_create(self, serializer):
        file = self.request.FILES.get('file')
        filename = file.name if file else ''
        serializer.save(
            uploaded_by=self.request.user,
            filename_original=filename,
        )

    @action(detail=True, methods=['patch'], url_path='review')
    def review(self, request, pk=None):
        upload = self.get_object()
        new_status = request.data.get('status')
        notes = request.data.get('notes', '')
        if new_status not in ('approved', 'printed', 'rejected'):
            return Response({'error': 'Invalid status.'}, status=status.HTTP_400_BAD_REQUEST)
        upload.status = new_status
        upload.notes = notes
        upload.reviewed_by = request.user
        upload.reviewed_at = timezone.now()
        upload.save()
        return Response(ExamPaperUploadSerializer(upload, context={'request': request}).data)

class ExamSetterAssignmentViewSet(viewsets.ModelViewSet):
    queryset = ExamSetterAssignment.objects.select_related(
        'session', 'subject', 'school_class', 'teacher', 'assigned_by'
    ).order_by('-created_at')
    serializer_class = ExamSetterAssignmentSerializer
    permission_classes = [permissions.IsAuthenticated, HasModuleAccess]
    module_key = "EXAMINATIONS"

    def get_queryset(self):
        qs = super().get_queryset()
        session = self.request.query_params.get('session')
        if session:
            qs = qs.filter(session_id=session)
        return qs

    def perform_create(self, serializer):
        serializer.save(assigned_by=self.request.user)

class ExamResultAnalyticsView(APIView):
    permission_classes = [permissions.IsAuthenticated, HasModuleAccess]
    module_key = "EXAMINATIONS"

    def get(self, request):
        paper_id = request.query_params.get('paper_id')
        if not paper_id:
            return Response({'error': 'paper_id required'}, status=status.HTTP_400_BAD_REQUEST)
        results = ExamResult.objects.filter(paper_id=paper_id)
        if not results.exists():
            return Response({'count': 0, 'average': 0, 'highest': 0, 'pass_count': 0, 'fail_count': 0})
        paper = ExamPaper.objects.get(pk=paper_id)
        agg = results.aggregate(avg=Avg('marks_obtained'), highest=Max('marks_obtained'))
        pass_count = results.filter(marks_obtained__gte=paper.pass_mark).count()
        return Response({
            'count': results.count(),
            'average': round(float(agg['avg'] or 0), 2),
            'highest': float(agg['highest'] or 0),
            'pass_count': pass_count,
            'fail_count': results.count() - pass_count,
        })
