from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.authentication import JWTAuthentication

# Paths a user with an outstanding forced password change is still allowed to
# hit — everything else is blocked. This is what makes an admin-issued
# temporary password unusable for real work: enforcement happens here, on the
# server, not just as a UI redirect the client could skip.
_ALLOWED_WHILE_MUST_CHANGE_PASSWORD = {
    "/api/auth/change-password/",
    "/api/auth/me/",
    "/api/auth/refresh/",
}


class ForcePasswordChangeJWTAuthentication(JWTAuthentication):
    """JWTAuthentication that locks an account down to a small allowlist of
    endpoints while `user.must_change_password` is set, regardless of what
    the access token otherwise grants."""

    def authenticate(self, request):
        result = super().authenticate(request)
        if result is None:
            return None
        user, validated_token = result
        if getattr(user, "must_change_password", False) and request.path not in _ALLOWED_WHILE_MUST_CHANGE_PASSWORD:
            raise AuthenticationFailed(
                "You must change your password before continuing.",
                code="password_change_required",
            )
        return result
