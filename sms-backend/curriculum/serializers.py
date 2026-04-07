from rest_framework import serializers
from .models import SchemeOfWork, SchemeTopic, LessonPlan, LearningResource

class SchemeTopicSerializer(serializers.ModelSerializer):
    class Meta:
        model = SchemeTopic
        fields = '__all__'

class SchemeOfWorkSerializer(serializers.ModelSerializer):
    topics = SchemeTopicSerializer(many=True, read_only=True)
    subject_name = serializers.CharField(source='subject.name', read_only=True)
    # allow_null so templates (no class/term) don't raise SerializerError
    school_class_name = serializers.SerializerMethodField()
    term_name = serializers.SerializerMethodField()

    class Meta:
        model = SchemeOfWork
        fields = '__all__'

    def get_school_class_name(self, obj):
        return obj.school_class.display_name if obj.school_class else None

    def get_term_name(self, obj):
        return obj.term.name if obj.term else None

class LessonPlanSerializer(serializers.ModelSerializer):
    topic_name = serializers.CharField(source='topic.topic', read_only=True)
    approved_by_name = serializers.CharField(source='approved_by.username', read_only=True)

    class Meta:
        model = LessonPlan
        fields = '__all__'

class LearningResourceSerializer(serializers.ModelSerializer):
    subject_name = serializers.CharField(source='subject.name', read_only=True)
    grade_level_name = serializers.CharField(source='grade_level.name', read_only=True)
    uploaded_by_name = serializers.CharField(source='uploaded_by.username', read_only=True)

    class Meta:
        model = LearningResource
        fields = '__all__'
