from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import AuthenticationFailed


class TenantAwareJWTAuthentication(JWTAuthentication):
    """
    Drop-in replacement for JWTAuthentication that validates the 'tenant_id'
    claim embedded in every SmartCampus JWT token against the current database
    schema context.

    Why this matters:
      - All SmartCampus JWT tokens embed a 'tenant_id' claim (e.g. 'olom' or
        'school_olomrynatyschoolapp') in get_token().
      - PlatformPublicSchemaMiddleware switches the DB connection to the public
        schema for /api/platform/* requests.
      - Without this check, a school admin's JWT (user_id=1, tenant_id='olom')
        would authenticate against the public schema where user_id=1 may be
        platform_admin — granting full platform access to a school user.

    This guard rejects any token whose tenant_id claim does not match the
    current connection.schema_name, making cross-schema token reuse impossible.
    """

    def authenticate(self, request):
        result = super().authenticate(request)
        if result is None:
            return None

        user, validated_token = result

        from django.db import connection as _conn
        from django_tenants.utils import get_public_schema_name as _public

        token_schema = validated_token.get('tenant_id')
        current_schema = getattr(_conn, 'schema_name', _public())

        if token_schema is None:
            # Token pre-dates the tenant_id claim. We cannot verify schema origin.
            # Deny access to public (platform) schema to prevent implicit elevation.
            if current_schema == _public():
                raise AuthenticationFailed(
                    'Token does not contain tenant context; re-authenticate to proceed.'
                )
            # For school-schema requests with old tokens, allow (conservative degradation).
            return (user, validated_token)

        if token_schema != current_schema:
            raise AuthenticationFailed(
                'Token was issued for a different schema and cannot be used here.'
            )

        return (user, validated_token)
