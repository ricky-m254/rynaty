from rest_framework import serializers
from .models import Club, ClubMembership, Tournament, StudentAward

class ClubSerializer(serializers.ModelSerializer):
    patron_name = serializers.CharField(source='patron.get_full_name', read_only=True)
    class Meta:
        model = Club
        fields = '__all__'

class ClubMembershipSerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(source='student.__str__', read_only=True)
    club_name = serializers.CharField(source='club.name', read_only=True)
    class Meta:
        model = ClubMembership
        fields = '__all__'

class TournamentSerializer(serializers.ModelSerializer):
    club_name = serializers.CharField(source='club.name', read_only=True)
    class Meta:
        model = Tournament
        fields = '__all__'

class StudentAwardSerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(source='student.__str__', read_only=True)
    class Meta:
        model = StudentAward
        fields = '__all__'
