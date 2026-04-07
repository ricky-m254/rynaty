from rest_framework import serializers
from .models import Visitor, AuthorizedPickup, StudentPickupLog

class VisitorSerializer(serializers.ModelSerializer):
    class Meta:
        model = Visitor
        fields = '__all__'

class AuthorizedPickupSerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(source='student.full_name', read_only=True)
    class Meta:
        model = AuthorizedPickup
        fields = '__all__'

class StudentPickupLogSerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(source='student.full_name', read_only=True)
    pickup_name = serializers.CharField(source='picked_up_by.guardian_name', read_only=True)
    class Meta:
        model = StudentPickupLog
        fields = '__all__'
