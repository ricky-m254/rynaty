from rest_framework import serializers
from .models import AlumniProfile, AlumniEvent, AlumniEventAttendee, AlumniMentorship, AlumniDonation

class AlumniProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = AlumniProfile
        fields = '__all__'

class AlumniEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = AlumniEvent
        fields = '__all__'

class AlumniEventAttendeeSerializer(serializers.ModelSerializer):
    alumni_name = serializers.CharField(source='alumni.first_name', read_only=True)
    event_title = serializers.CharField(source='event.title', read_only=True)

    class Meta:
        model = AlumniEventAttendee
        fields = '__all__'


class AlumniMentorshipSerializer(serializers.ModelSerializer):
    mentor_name = serializers.SerializerMethodField()
    mentor_occupation = serializers.ReadOnlyField(source='mentor.current_occupation')

    class Meta:
        model = AlumniMentorship
        fields = '__all__'

    def get_mentor_name(self, obj):
        return f"{obj.mentor.first_name} {obj.mentor.last_name}"


class AlumniDonationSerializer(serializers.ModelSerializer):
    alumni_name = serializers.SerializerMethodField()
    alumni_graduation_year = serializers.ReadOnlyField(source='alumni.graduation_year')

    class Meta:
        model = AlumniDonation
        fields = '__all__'

    def get_alumni_name(self, obj):
        if obj.is_anonymous:
            return 'Anonymous'
        return f"{obj.alumni.first_name} {obj.alumni.last_name}"
