from rest_framework import serializers
from .models import ExamSession, ExamPaper, ExamSeatAllocation, ExamResult, ExamGradeBoundary, ExamPaperUpload, ExamSetterAssignment

class ExamSessionSerializer(serializers.ModelSerializer):
    class Meta:
        model = ExamSession
        fields = '__all__'

class ExamPaperSerializer(serializers.ModelSerializer):
    subject_name = serializers.CharField(source='subject.name', read_only=True)
    class_name = serializers.CharField(source='school_class.display_name', read_only=True)
    session_name = serializers.CharField(source='session.name', read_only=True)
    invigilator_name = serializers.SerializerMethodField()

    class Meta:
        model = ExamPaper
        fields = '__all__'

    def get_invigilator_name(self, obj):
        if obj.invigilator_id:
            return obj.invigilator.get_full_name() or obj.invigilator.username
        return ''

class ExamSeatAllocationSerializer(serializers.ModelSerializer):
    student_name = serializers.SerializerMethodField()
    admission_number = serializers.CharField(source='student.admission_number', read_only=True)

    class Meta:
        model = ExamSeatAllocation
        fields = '__all__'

    def get_student_name(self, obj):
        return f"{obj.student.first_name} {obj.student.last_name}".strip()

class ExamResultSerializer(serializers.ModelSerializer):
    student_name = serializers.SerializerMethodField()
    admission_number = serializers.CharField(source='student.admission_number', read_only=True)
    session = serializers.IntegerField(source='paper.session_id', read_only=True)
    session_name = serializers.CharField(source='paper.session.name', read_only=True)
    paper_name = serializers.SerializerMethodField()
    subject_name = serializers.SerializerMethodField()
    class_name = serializers.SerializerMethodField()

    class Meta:
        model = ExamResult
        fields = '__all__'

    def validate(self, attrs):
        attrs = super().validate(attrs)
        is_absent = attrs.get('is_absent')
        if is_absent is None and self.instance is not None:
            is_absent = self.instance.is_absent

        if is_absent:
            attrs['marks_obtained'] = None
            attrs['grade'] = ''
            attrs['position'] = None
            return attrs

        marks = attrs.get('marks_obtained')
        if marks is None and self.instance is not None:
            marks = self.instance.marks_obtained
        if marks is None:
            raise serializers.ValidationError(
                {'marks_obtained': 'This field is required unless the student is marked absent.'}
            )
        return attrs

    def get_student_name(self, obj):
        return f"{obj.student.first_name} {obj.student.last_name}".strip()

    def get_paper_name(self, obj):
        if not obj.paper_id:
            return ''
        return f"{obj.paper.subject.name} - {obj.paper.school_class}"

    def get_subject_name(self, obj):
        return obj.paper.subject.name if obj.paper_id else ''

    def get_class_name(self, obj):
        return str(obj.paper.school_class) if obj.paper_id else ''

class ExamGradeBoundarySerializer(serializers.ModelSerializer):
    class Meta:
        model = ExamGradeBoundary
        fields = '__all__'

class ExamPaperUploadSerializer(serializers.ModelSerializer):
    uploaded_by_name = serializers.SerializerMethodField()
    reviewed_by_name = serializers.SerializerMethodField()
    subject_name = serializers.CharField(source='subject.name', read_only=True)
    class_name = serializers.CharField(source='school_class.display_name', read_only=True)
    session_name = serializers.CharField(source='session.name', read_only=True)
    file_url = serializers.SerializerMethodField()
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = ExamPaperUpload
        fields = '__all__'
        extra_kwargs = {
            'uploaded_by': {'required': False},
            'file': {'required': True},
        }

    def get_uploaded_by_name(self, obj):
        return obj.uploaded_by.get_full_name() or obj.uploaded_by.username if obj.uploaded_by_id else ''

    def get_reviewed_by_name(self, obj):
        return obj.reviewed_by.get_full_name() or obj.reviewed_by.username if obj.reviewed_by_id else ''

    def get_file_url(self, obj):
        request = self.context.get('request')
        if obj.file and request:
            return request.build_absolute_uri(obj.file.url)
        return None

class ExamSetterAssignmentSerializer(serializers.ModelSerializer):
    teacher_name = serializers.SerializerMethodField()
    subject_name = serializers.CharField(source='subject.name', read_only=True)
    class_name = serializers.CharField(source='school_class.display_name', read_only=True)
    session_name = serializers.CharField(source='session.name', read_only=True)
    assigned_by_name = serializers.SerializerMethodField()

    class Meta:
        model = ExamSetterAssignment
        fields = '__all__'
        extra_kwargs = {
            'assigned_by': {'required': False},
        }

    def get_teacher_name(self, obj):
        return obj.teacher.get_full_name() or obj.teacher.username

    def get_assigned_by_name(self, obj):
        return obj.assigned_by.get_full_name() or obj.assigned_by.username if obj.assigned_by_id else ''
