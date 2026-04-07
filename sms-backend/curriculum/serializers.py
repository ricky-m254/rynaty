from rest_framework import serializers
from .models import SchemeOfWork, SchemeTopic, LessonPlan, LearningResource

class SchemeTopicSerializer(serializers.ModelSerializer):
    class Meta:
        model = SchemeTopic
        fields = '__all__'

class SchemeOfWorkSerializer(serializers.ModelSerializer):
    topics = SchemeTopicSerializer(many=True, read_only=True)
    subject_name = serializers.CharField(source='subject.name', read_only=True)
    school_class_name = serializers.CharField(source='school_class.display_name', read_only=True)
    term_name = serializers.CharField(source='term.name', read_only=True)

    class Meta:
        model = SchemeOfWork
        fields = '__all__'

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
