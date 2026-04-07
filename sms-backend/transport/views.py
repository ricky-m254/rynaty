from datetime import date
from django.conf import settings
from rest_framework import viewsets, permissions, status
from rest_framework.views import APIView
from rest_framework.response import Response
from school.permissions import HasModuleAccess, IsSchoolAdmin
from .models import Vehicle, Route, RouteStop, StudentTransport, TransportIncident
from .serializers import (
    VehicleSerializer, RouteSerializer, RouteStopSerializer,
    StudentTransportSerializer, TransportIncidentSerializer
)

class VehicleViewSet(viewsets.ModelViewSet):
    queryset = Vehicle.objects.all()
    serializer_class = VehicleSerializer
    permission_classes = [permissions.IsAuthenticated, HasModuleAccess]
    module_key = "TRANSPORT"
    filterset_fields = ['status']

class RouteViewSet(viewsets.ModelViewSet):
    queryset = Route.objects.all()
    serializer_class = RouteSerializer
    permission_classes = [permissions.IsAuthenticated, HasModuleAccess]
    module_key = "TRANSPORT"
    filterset_fields = ['vehicle', 'is_active']

class RouteStopViewSet(viewsets.ModelViewSet):
    queryset = RouteStop.objects.all()
    serializer_class = RouteStopSerializer
    permission_classes = [permissions.IsAuthenticated, HasModuleAccess]
    module_key = "TRANSPORT"
    filterset_fields = ['route']

class StudentTransportViewSet(viewsets.ModelViewSet):
    queryset = StudentTransport.objects.all()
    serializer_class = StudentTransportSerializer
    permission_classes = [permissions.IsAuthenticated, HasModuleAccess]
    module_key = "TRANSPORT"
    filterset_fields = ['route', 'is_active', 'term']

class TransportIncidentViewSet(viewsets.ModelViewSet):
    queryset = TransportIncident.objects.all()
    serializer_class = TransportIncidentSerializer
    permission_classes = [permissions.IsAuthenticated, HasModuleAccess]
    module_key = "TRANSPORT"
    filterset_fields = ['vehicle', 'resolved']

class TransportDashboardView(APIView):
    permission_classes = [permissions.IsAuthenticated, HasModuleAccess]
    module_key = "TRANSPORT"

    def get(self, request):
        return Response({
            "total_vehicles": Vehicle.objects.count(),
            "active_routes": Route.objects.filter(is_active=True).count(),
            "students_enrolled": StudentTransport.objects.filter(is_active=True).count(),
            "incidents_open": TransportIncident.objects.filter(resolved=False).count(),
        })


SEED_VEHICLES = [
    {"registration": "KAA 001B", "make": "Toyota",   "model": "Coaster",   "capacity": 40, "status": "Active",      "notes": "Westlands route bus"},
    {"registration": "KBB 002C", "make": "Isuzu",    "model": "FRR",       "capacity": 40, "status": "Active",      "notes": "Kibera route bus"},
    {"registration": "KCC 003D", "make": "Toyota",   "model": "Coaster",   "capacity": 35, "status": "Maintenance", "notes": "Karen route bus – in service"},
    {"registration": "KDD 004E", "make": "Mitsubishi","model": "Rosa",      "capacity": 40, "status": "Active",      "notes": "Eastlands route bus"},
]

SEED_ROUTES = [
    {
        "name": "Westlands Route", "direction": "BOTH", "is_active": True, "notes": "Morning pick-up and evening drop-off",
        "stops": [
            {"stop_name": "Westlands Rongi",  "sequence": 1, "estimated_time": "06:15"},
            {"stop_name": "ABC Place",         "sequence": 2, "estimated_time": "06:22"},
            {"stop_name": "Westgate Mall",     "sequence": 3, "estimated_time": "06:30"},
            {"stop_name": "Chiromo Rd",        "sequence": 4, "estimated_time": "06:40"},
            {"stop_name": "School Gate",       "sequence": 5, "estimated_time": "06:55"},
        ]
    },
    {
        "name": "Kibera Route", "direction": "BOTH", "is_active": True, "notes": "Serves Kibera and surrounding areas",
        "stops": [
            {"stop_name": "Olympic Estate",   "sequence": 1, "estimated_time": "06:10"},
            {"stop_name": "Lindi",            "sequence": 2, "estimated_time": "06:18"},
            {"stop_name": "Laini Saba",       "sequence": 3, "estimated_time": "06:25"},
            {"stop_name": "Lang'ata Rd",      "sequence": 4, "estimated_time": "06:35"},
            {"stop_name": "School Gate",      "sequence": 5, "estimated_time": "06:50"},
        ]
    },
    {
        "name": "Karen Route", "direction": "BOTH", "is_active": True, "notes": "Karen, Hardy and Carnivore area",
        "stops": [
            {"stop_name": "Karen Shopping Centre", "sequence": 1, "estimated_time": "06:05"},
            {"stop_name": "Hardy",                 "sequence": 2, "estimated_time": "06:15"},
            {"stop_name": "Lang'ata Rd Junction",  "sequence": 3, "estimated_time": "06:28"},
            {"stop_name": "Carnivore Junction",    "sequence": 4, "estimated_time": "06:42"},
            {"stop_name": "School Gate",           "sequence": 5, "estimated_time": "07:00"},
        ]
    },
    {
        "name": "Eastlands Route", "direction": "BOTH", "is_active": True, "notes": "Umoja, Jogoo Rd corridor",
        "stops": [
            {"stop_name": "Umoja Estate",    "sequence": 1, "estimated_time": "05:58"},
            {"stop_name": "Jogoo Rd",        "sequence": 2, "estimated_time": "06:10"},
            {"stop_name": "Milimani Rd",     "sequence": 3, "estimated_time": "06:22"},
            {"stop_name": "Ngara",           "sequence": 4, "estimated_time": "06:35"},
            {"stop_name": "School Gate",     "sequence": 5, "estimated_time": "06:48"},
        ]
    },
]

SEED_INCIDENTS = [
    {"incident_date": date.today(), "description": "Minor delay on Westlands route due to traffic at Chiromo bridge.", "severity": "Minor", "reported_by": "John Kamau", "resolved": False},
]


class TransportSeedView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsSchoolAdmin]

    def post(self, request):
        tenant = getattr(request, "tenant", None)
        schema = getattr(tenant, "schema_name", None)
        if not settings.DEBUG and schema != "demo_school":
            return Response(
                {"detail": "Transport sample seeding is disabled outside debug and demo environments."},
                status=status.HTTP_403_FORBIDDEN,
            )

        created_vehicles = 0
        created_routes = 0
        created_stops = 0
        created_incidents = 0

        vehicles_map = {}
        for i, vd in enumerate(SEED_VEHICLES):
            v, created = Vehicle.objects.get_or_create(
                registration=vd["registration"],
                defaults={k: v2 for k, v2 in vd.items() if k != "registration"}
            )
            if created:
                created_vehicles += 1
            vehicles_map[i] = v

        for i, rd in enumerate(SEED_ROUTES):
            stops_data = rd.pop("stops", [])
            route, created = Route.objects.get_or_create(
                name=rd["name"],
                defaults={**rd, "vehicle": vehicles_map.get(i)}
            )
            if created:
                created_routes += 1
            for sd in stops_data:
                _, s_created = RouteStop.objects.get_or_create(
                    route=route, sequence=sd["sequence"],
                    defaults=sd
                )
                if s_created:
                    created_stops += 1
            rd["stops"] = stops_data

        if vehicles_map:
            first_vehicle = vehicles_map[0]
            for inc in SEED_INCIDENTS:
                _, i_created = TransportIncident.objects.get_or_create(
                    vehicle=first_vehicle,
                    incident_date=inc["incident_date"],
                    defaults=inc
                )
                if i_created:
                    created_incidents += 1

        return Response({
            "detail": "Transport sample data seeded successfully.",
            "created": {
                "vehicles": created_vehicles,
                "routes": created_routes,
                "stops": created_stops,
                "incidents": created_incidents,
            }
        }, status=status.HTTP_201_CREATED)
