import secrets
import string

from rest_framework import generics, permissions, viewsets, status
from rest_framework.decorators import action
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.response import Response
from rest_framework_simplejwt.views import TokenObtainPairView
from django.contrib.auth import get_user_model
from django.db.models import Count, Q

from accounts.lockout import client_ip, clear_failures, is_locked, register_failure
from accounts.models import Role
from accounts.permissions import IsAdministrator, IsAdminOrStaff
from children.models import Child
from accounts.serializers import (
    LoginSerializer, UserSerializer, UserWriteSerializer, RoleSerializer,
    ChangePasswordSerializer,
)
from activity.models import ActivityLog
from activity.services import log_activity

User = get_user_model()

# Unambiguous alphabet for admin-issued temporary passwords — excludes
# characters that are easy to mis-key/mis-read: 0/O, 1/l/I.
_AMBIGUOUS_CHARS = set("0O1lI")
_TEMP_PASSWORD_ALPHABET = "".join(
    c for c in string.ascii_letters + string.digits if c not in _AMBIGUOUS_CHARS)


def _generate_temp_password(length=12):
    return "".join(secrets.choice(_TEMP_PASSWORD_ALPHABET) for _ in range(length))


class LoginView(TokenObtainPairView):
    serializer_class = LoginSerializer

    def post(self, request, *args, **kwargs):
        email = request.data.get("email", "") or ""
        ip = client_ip(request)

        # Locked means locked — don't even attempt authentication, correct
        # credentials or not, and never reveal whether the account exists.
        locked, retry_after = is_locked(email, ip)
        if locked:
            minutes = (retry_after + 59) // 60  # round up to whole minutes
            return Response(
                {"detail": f"Too many failed login attempts. Try again in {minutes} minute(s)."},
                status=status.HTTP_429_TOO_MANY_REQUESTS)

        try:
            response = super().post(request, *args, **kwargs)
        except AuthenticationFailed:
            self._register_failure(email, ip)
            raise

        clear_failures(email, ip)
        return response

    def _register_failure(self, email, ip):
        _locked, _retry_after, new_lockout = register_failure(email, ip)
        if new_lockout:
            # No authenticated actor caused this — the system locked the
            # account/IP out. log_activity accepts actor=None (logged as
            # "System"), so there's no need to look up the user.
            log_activity(
                None, ActivityLog.UPDATED, ActivityLog.SECURITY,
                entity_type="User",
                entity_label=f"Login locked for {email} after repeated failures")


class MeView(generics.RetrieveAPIView):
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return self.request.user


class ChangePasswordView(generics.GenericAPIView):
    serializer_class = ChangePasswordSerializer
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = self.get_serializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        log_activity(
            request.user, ActivityLog.UPDATED, ActivityLog.SECURITY,
            entity_type="User", entity_label="Changed own password", entity_id=request.user.id)
        return Response({"detail": "Password changed."}, status=status.HTTP_200_OK)


class UserViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAdministrator]
    pagination_class = None

    def get_queryset(self):
        qs = User.objects.all().order_by("last_name", "first_name")
        if self.request.query_params.get("include_archived") != "true":
            qs = qs.exclude(status=User.ARCHIVED)
        return qs

    def get_serializer_class(self):
        if self.action in ("create", "update", "partial_update"):
            return UserWriteSerializer
        return UserSerializer

    def _log(self, user, action_name):
        log_activity(
            self.request.user, action_name, ActivityLog.USER,
            entity_type="User",
            entity_label=(user.fullname or user.email),
            entity_id=user.id)

    def create(self, request, *args, **kwargs):
        """Create a user with a server-generated temporary password, returned
        exactly once (same contract as reset_password). Any client-supplied
        password is ignored by the serializer."""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        temp_password = _generate_temp_password()
        user.set_password(temp_password)
        user.must_change_password = True
        update_fields = ["password", "must_change_password", "updated_at"]
        # Single-admin handover: a new Administrator created while another
        # admin is active takes over at first login (accounts/serializers.py).
        if (user.role and user.role.role_name == Role.ADMINISTRATOR
                and User.objects.filter(role__role_name=Role.ADMINISTRATOR,
                                        status=User.ACTIVE).exclude(pk=user.pk).exists()):
            user.admin_takeover_pending = True
            update_fields.append("admin_takeover_pending")
        user.save(update_fields=update_fields)
        self._log(user, ActivityLog.CREATED)
        data = UserSerializer(user).data
        data["temp_password"] = temp_password
        return Response(data, status=status.HTTP_201_CREATED)

    def perform_update(self, serializer):
        user = serializer.save()
        self._log(user, ActivityLog.UPDATED)

    @action(detail=True, methods=["post"])
    def archive(self, request, pk=None):
        user = self.get_object()
        user.status = User.ARCHIVED
        user.is_active = False
        user.save(update_fields=["status", "is_active", "updated_at"])
        self._log(user, ActivityLog.ARCHIVED)
        return Response({"status": "archived"}, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"], url_path="reset-password")
    def reset_password(self, request, pk=None):
        """Admin-issued temporary password. Never accepts a password from the
        request — always generated server-side and returned exactly once."""
        user = self.get_object()
        if user.status == User.ARCHIVED or not user.is_active:
            return Response(
                {"detail": "Cannot reset the password for an inactive or archived user."},
                status=status.HTTP_400_BAD_REQUEST)
        temp_password = _generate_temp_password()
        user.set_password(temp_password)
        user.must_change_password = True
        user.save(update_fields=["password", "must_change_password", "updated_at"])
        self._log(user, ActivityLog.UPDATED)
        return Response({"temp_password": temp_password}, status=status.HTTP_200_OK)


class RoleListView(generics.ListAPIView):
    permission_classes = [IsAdministrator]
    pagination_class = None
    serializer_class = RoleSerializer

    def get_queryset(self):
        return Role.objects.all().order_by("role_name")


class PsychologistListView(generics.GenericAPIView):
    """Active psychologists + current caseload (active assigned children).
    Admin + Staff so Staff can populate the assign picker and gauge workload."""
    permission_classes = [IsAdminOrStaff]
    pagination_class = None

    def get(self, request):
        qs = (User.objects
              .filter(role__role_name=Role.PSYCHOLOGIST, status=User.ACTIVE)
              .annotate(caseload=Count("assigned_children",
                                       filter=Q(assigned_children__status=Child.ACTIVE)))
              .order_by("last_name", "first_name"))
        return Response([
            {"id": p.id, "name": p.fullname or p.email, "caseload": p.caseload} for p in qs
        ])
