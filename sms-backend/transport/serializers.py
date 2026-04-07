from rest_framework import serializers
from .models import Vehicle, Route, RouteStop, StudentTransport, TransportIncident

class VehicleSerializer(serializers.ModelSerializer):
    driver_name = serializers.CharField(source='driver.first_name', read_only=True)
    class Meta:
        model = Vehicle
        fields = '__all__'

class RouteStopSerializer(serializers.ModelSerializer):
    class Meta:
        model = RouteStop
        fields = '__all__'

class RouteSerializer(serializers.ModelSerializer):
    stops = RouteStopSerializer(many=True, read_only=True)
    vehicle_registration = serializers.CharField(source='vehicle.registration', read_only=True)
    class Meta:
        model = Route
        fields = '__all__'

class StudentTransportSerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(source='student.full_name', read_only=True)
    route_name = serializers.CharField(source='route.name', read_only=True)
    stop_name = serializers.CharField(source='boarding_stop.stop_name', read_only=True)
    class Meta:
        model = StudentTransport
        fields = '__all__'

class TransportIncidentSerializer(serializers.ModelSerializer):
    vehicle_registration = serializers.CharField(source='vehicle.registration', read_only=True)
    class Meta:
        model = TransportIncident
        fields = '__all__'
