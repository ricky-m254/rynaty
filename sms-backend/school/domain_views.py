"""
School-Admin Custom Domain Onboarding Views
Endpoints scoped to the authenticated tenant admin.
These read/write to the *public* schema via domain_service.
"""
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django_tenants.utils import schema_context

from clients import domain_service
from clients.models import Tenant
from .permissions import CanManageSystemSettings


def _get_tenant(request) -> Tenant | None:
    """
    Return the Tenant instance for the current request.
    Relies on TenantContextGuardMiddleware having set connection.schema_name.
    """
    request_tenant = getattr(request, "tenant", None)
    schema = getattr(request_tenant, "schema_name", None)

    if not schema:
        from django.db import connection
        schema = connection.schema_name

    if not schema or schema == "public":
        return None
    with schema_context("public"):
        return Tenant.objects.filter(schema_name=schema).first()


class SchoolDomainStatusView(APIView):
    """
    GET  /api/settings/domain/           — current domain request status
    POST /api/settings/domain/request/   — initiate / reset domain request
    POST /api/settings/domain/verify/    — trigger DNS TXT verification
    DELETE /api/settings/domain/         — cancel pending request
    """
    permission_classes = [CanManageSystemSettings]

    def get(self, request):
        with schema_context("public"):
            tenant = _get_tenant(request)
            if not tenant:
                return Response({"error": "Tenant not found."}, status=404)
            data = domain_service.get_current_request(tenant)
        return Response(data or {"status": None, "message": "No domain request found."})

    def delete(self, request):
        with schema_context("public"):
            tenant = _get_tenant(request)
            if not tenant:
                return Response({"error": "Tenant not found."}, status=404)
            from clients.models import CustomDomainRequest
            deleted, _ = CustomDomainRequest.objects.filter(
                tenant=tenant,
                status__in=[
                    CustomDomainRequest.STATUS_PENDING,
                    CustomDomainRequest.STATUS_FAILED,
                ],
            ).delete()
        if deleted:
            return Response({"message": "Domain request cancelled."})
        return Response({"error": "No cancellable request found."}, status=400)


class SchoolDomainRequestView(APIView):
    permission_classes = [CanManageSystemSettings]

    def post(self, request):
        requested_domain = request.data.get("domain", "").strip()
        if not requested_domain:
            return Response({"error": "A domain name is required."}, status=400)

        with schema_context("public"):
            tenant = _get_tenant(request)
            if not tenant:
                return Response({"error": "Tenant not found."}, status=404)
            try:
                result = domain_service.initiate_domain_request(
                    tenant=tenant,
                    requested_domain=requested_domain,
                    requested_by=request.user.username,
                )
            except ValueError as exc:
                return Response({"error": str(exc)}, status=400)

        return Response(result, status=status.HTTP_201_CREATED)


class SchoolDomainVerifyView(APIView):
    permission_classes = [CanManageSystemSettings]

    def post(self, request):
        with schema_context("public"):
            tenant = _get_tenant(request)
            if not tenant:
                return Response({"error": "Tenant not found."}, status=404)
            try:
                result = domain_service.verify_domain_request(tenant)
            except ValueError as exc:
                return Response({"error": str(exc)}, status=400)

        verified = result["status"] == "VERIFIED"
        return Response(
            {
                **result,
                "message": (
                    "DNS record verified! Your domain is now pending platform activation."
                    if verified
                    else "DNS TXT record not found yet. Please ensure the record has propagated and try again."
                ),
            },
            status=200 if verified else 202,
        )
