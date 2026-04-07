from rest_framework import serializers
from .models import Course, CourseMaterial, OnlineQuiz, QuizQuestion, QuizAttempt, VirtualSession


class CourseMaterialSerializer(serializers.ModelSerializer):
    course_name = serializers.CharField(source='course.title', read_only=True)

    class Meta:
        model = CourseMaterial
        fields = '__all__'


class QuizQuestionSerializer(serializers.ModelSerializer):
    class Meta:
        model = QuizQuestion
        fields = '__all__'


class VirtualSessionSerializer(serializers.ModelSerializer):
    course_name = serializers.CharField(source='course.title', read_only=True)

    class Meta:
        model = VirtualSession
        fields = '__all__'


class OnlineQuizSerializer(serializers.ModelSerializer):
    question_count = serializers.SerializerMethodField()
    attempt_count = serializers.SerializerMethodField()
    course_name = serializers.CharField(source='course.title', read_only=True)
    subject_name = serializers.SerializerMethodField()

    class Meta:
        model = OnlineQuiz
        fields = '__all__'

    def get_question_count(self, obj):
        return obj.questions.count()

    def get_attempt_count(self, obj):
        return obj.attempts.count()

    def get_subject_name(self, obj):
        if obj.course and obj.course.subject:
            return obj.course.subject.name
        return ''


class CourseSerializer(serializers.ModelSerializer):
    teacher_name = serializers.SerializerMethodField()
    subject_name = serializers.SerializerMethodField()
    school_class_name = serializers.SerializerMethodField()
    material_count = serializers.SerializerMethodField()

    class Meta:
        model = Course
        fields = '__all__'
        extra_kwargs = {
            'teacher': {'required': False},
        }

    def get_teacher_name(self, obj):
        if obj.teacher:
            return obj.teacher.get_full_name() or obj.teacher.username
        return ''

    def get_subject_name(self, obj):
        return obj.subject.name if obj.subject else ''

    def get_school_class_name(self, obj):
        return str(obj.school_class) if obj.school_class else ''

    def get_material_count(self, obj):
        return obj.materials.count()


class QuizAttemptSerializer(serializers.ModelSerializer):
    student_name = serializers.SerializerMethodField()
    quiz_title = serializers.SerializerMethodField()

    class Meta:
        model = QuizAttempt
        fields = '__all__'

    def get_student_name(self, obj):
        return f"{obj.student.first_name} {obj.student.last_name}"

    def get_quiz_title(self, obj):
        return obj.quiz.title
