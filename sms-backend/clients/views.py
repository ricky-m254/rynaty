from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny

class PingView(APIView):
    """
    Validation Baseline: Unauthenticated connectivity check.
    Must be reachable from Frontend before any feature work.
    """
    permission_classes = [AllowAny]

    def get(self, request):
        return Response({
            "status": "success",
            "message": "Backend is reachable",
            "service": "SMS Backend API"
        })