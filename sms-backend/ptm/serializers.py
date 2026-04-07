from rest_framework import serializers
from .models import PTMSession, PTMSlot, PTMBooking

class PTMSessionSerializer(serializers.ModelSerializer):
    class Meta:
        model = PTMSession
        fields = '__all__'

class PTMSlotSerializer(serializers.ModelSerializer):
    class Meta:
        model = PTMSlot
        fields = '__all__'

class PTMBookingSerializer(serializers.ModelSerializer):
    class Meta:
        model = PTMBooking
        fields = '__all__'
