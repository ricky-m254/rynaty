"""
JWTService — Phase 11, Prompt 29.

Responsibilities:
- Generate JWT token with user ID and role
- Validate token
- Attach user ID and role to token payload

Note: This wraps Django REST Framework Simple JWT.
      The existing /api/auth/login/ endpoint is NOT modified.
"""
from __future__ import annotations
from typing import Optional


class JWTService:
    """Application service for JWT token generation and validation."""

    def generate_token_pair(self, user_id: int, role: str | None) -> dict:
        """
        Generate access + refresh token pair.
        Delegates to SimpleJWT internals for actual signing.
        Returns: {"access": "...", "refresh": "...", "user_id": ..., "role": ...}
        """
        from rest_framework_simplejwt.tokens import RefreshToken
        from django.contrib.auth import get_user_model

        User = get_user_model()
        try:
            user = User.objects.get(pk=user_id)
        except User.DoesNotExist:
            raise ValueError(f"User with id={user_id} does not exist.")

        refresh = RefreshToken.for_user(user)
        refresh["role"] = role or ""
        return {
            "access": str(refresh.access_token),
            "refresh": str(refresh),
            "user_id": user_id,
            "role": role,
        }

    def decode_token(self, token: str) -> dict:
        """Decode and validate a JWT access token. Returns the payload."""
        from rest_framework_simplejwt.tokens import AccessToken
        payload = AccessToken(token)
        return dict(payload)

    def extract_user_id(self, token: str) -> Optional[int]:
        try:
            payload = self.decode_token(token)
            return payload.get("user_id")
        except Exception:
            return None

    def extract_role(self, token: str) -> Optional[str]:
        try:
            payload = self.decode_token(token)
            return payload.get("role")
        except Exception:
            return None
