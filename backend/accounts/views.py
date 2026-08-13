import secrets
import string

from rest_framework import generics, permissions, viewsets, status
from rest_framework.decorators import action
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.response import Response
from rest_framework_simplejwt.views import TokenObtainPairView
from django.contrib.auth import get_user_model
from django.db.models import Count, Q

from accounts.google_auth import (
    AccessRequestPending, SignupThrottled, link_google_account,
    resolve_google_user, verify_google_credential,
)
from accounts.lockout import client_ip, clear_failures, is_locked, register_failure
from accounts.models import Role
from accounts.permissions import IsAdministrator, IsAdminOrStaff
from children.models import Child
from accounts.serializers import (
    LoginSerializer, UserSerializer, UserWriteSerializer, RoleSerializer,
    ChangePasswordSerializer,
)
from activity.models import ActivityLog
from activity.serializers import ActivityLogSerializer
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


class GoogleLoginView(generics.GenericAPIView):
    """Exchange a Google ID token for this system's own JWT pair.

    Returns the same {refresh, access, user} shape as LoginView, so the
    frontend stores the session identically however the user signed in.
    """

    # No authenticators on purpose: a stale or expired access token sitting in
    # the browser must not stop someone from signing in again. The cost is
    # that DRF would render AuthenticationFailed as 403 (it downgrades 401
    # when a view exposes no WWW-Authenticate scheme), so the 401 is returned
    # explicitly below — this is an authentication endpoint and callers, the
    # frontend included, branch on that status.
    permission_classes = [permissions.AllowAny]
    authentication_classes = []
    serializer_class = None

    def post(self, request):
        try:
            claims = verify_google_credential(request.data.get("credential"))
            user = resolve_google_user(
                claims, request.data.get("requested_role"), ip=client_ip(request))
        except SignupThrottled as exc:
            return Response({"detail": exc.detail},
                            status=status.HTTP_429_TOO_MANY_REQUESTS)
        except AccessRequestPending as exc:
            # 403, not 401: Google authenticated them fine — this system has
            # simply not authorised them yet. The distinct status and `state`
            # let the login page show a waiting screen instead of an error the
            # person would retry forever.
            return Response(
                {"detail": exc.detail, "state": "pending_approval",
                 "role_required": exc.role_required},
                status=status.HTTP_403_FORBIDDEN)
        except AuthenticationFailed as exc:
            return Response({"detail": exc.detail},
                            status=status.HTTP_401_UNAUTHORIZED)

        newly_linked = link_google_account(user, claims)

        # Reuse LoginSerializer.get_token so the access token carries the same
        # role claim as a password login — anything reading it downstream
        # cannot tell the two paths apart.
        refresh = LoginSerializer.get_token(user)

        if newly_linked:
            log_activity(
                user, ActivityLog.UPDATED, ActivityLog.SECURITY,
                entity_type="User", entity_id=user.id,
                entity_label="Linked Google account for sign-in")
        log_activity(user, ActivityLog.LOGIN, ActivityLog.SECURITY)

        return Response({
            "refresh": str(refresh),
            "access": str(refresh.access_token),
            "user": UserSerializer(user).data,
        }, status=status.HTTP_200_OK)


class GoogleAuthConfigView(generics.GenericAPIView):
    """Tells the login page whether to render the Google button.

    The client ID is public by design (it ships in the page anyway), but
    serving it from here means the frontend does not need a rebuild to turn
    Google Sign-In on or off — only the API's environment changes.
    """

    permission_classes = [permissions.AllowAny]
    authentication_classes = []
    serializer_class = None

    def get(self, request):
        from django.conf import settings as django_settings
        client_id = django_settings.GOOGLE_OAUTH_CLIENT_ID
        return Response({
            "enabled": bool(client_id),
            "client_id": client_id,
            "allowed_domains": django_settings.GOOGLE_ALLOWED_DOMAINS,
        })


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
        # Hiding archived users is a *list* concern only. Detail routes have to
        # reach a deactivated account by id — otherwise reactivate/ is
        # unreachable for exactly the users it exists to serve.
        if self.action == "list" and self.request.query_params.get("include_archived") != "true":
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
        # is_active follows status automatically (User.save).
        user.save(update_fields=["status", "updated_at"])
        self._log(user, ActivityLog.ARCHIVED)
        return Response({"status": "archived"}, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"])
    def reactivate(self, request, pk=None):
        """Undo a deactivation. Administrators are deliberately excluded: a
        deactivated administrator can only come back through a brand-new
        account (product decision 2026-07-18), and a reactivate route would
        quietly reopen the handover path that decision closed.

        The old password is left working — an account is usually deactivated
        when someone leaves, so it is flagged for a forced change instead:
        whoever comes back signs in once with the old credentials and has to
        set a new password before they reach any case data."""
        user = self.get_object()
        if user.status != User.ARCHIVED:
            return Response({"detail": "This account is already active."},
                            status=status.HTTP_400_BAD_REQUEST)
        if user.role and user.role.role_name == Role.ADMINISTRATOR:
            return Response(
                {"detail": "A deactivated administrator cannot be reactivated. "
                           "Create a new administrator account instead."},
                status=status.HTTP_400_BAD_REQUEST)
        user.status = User.ACTIVE
        user.must_change_password = True
        user.save(update_fields=["status", "must_change_password", "updated_at"])
        self._log(user, ActivityLog.UPDATED)
        return Response({"status": user.status}, status=status.HTTP_200_OK)

    @action(detail=True, methods=["get"])
    def activity(self, request, pk=None):
        """This account's recent history, both directions.

        What they DID answers the question an agency accountable under RA
        10173 actually has to answer — who opened this child's record. What was
        done TO the account is the other half of the same story: who issued
        them a password, who approved them, who deactivated them. Either alone
        leaves a gap someone could hide in, so the two streams are merged and
        each entry says which it is.
        """
        user = self.get_object()
        entries = list(
            ActivityLog.objects
            .filter(Q(actor=user) | Q(entity_type="User", entity_id=user.id))
            .order_by("-created_at")[:25])
        data = ActivityLogSerializer(entries, many=True).data
        for row, entry in zip(data, entries):
            # The drawer has to distinguish "she archived a case" from "her
            # account was archived" — same verb, opposite meaning.
            row["by_them"] = entry.actor_id == user.id
        return Response(data)

    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        """Grant a pending Google sign-up its role and let it in.

        The role must be supplied explicitly. There is deliberately NO fallback
        to `requested_role`: the applicant's claim is a hint for the dropdown,
        and defaulting to it would quietly turn every request that omitted the
        field into self-assignment — which is the exact thing this whole flow
        exists to prevent.
        """
        user = self.get_object()
        if user.status != User.PENDING:
            return Response({"detail": "This account is not awaiting approval."},
                            status=status.HTTP_400_BAD_REQUEST)

        role_id = request.data.get("role")
        if not role_id:
            return Response({"role": "Choose the role this account should have."},
                            status=status.HTTP_400_BAD_REQUEST)
        role = Role.objects.filter(pk=role_id).first()
        if role is None:
            return Response({"role": "Unknown role."},
                            status=status.HTTP_400_BAD_REQUEST)
        # Approving cannot mint an administrator. That account is the agency's
        # recovery path and carries the single-admin handover rule with it;
        # reaching it through this door would route around both.
        if role.role_name == Role.ADMINISTRATOR:
            return Response(
                {"role": "An administrator cannot be created by approving a "
                         "request. Add the account from User Management instead."},
                status=status.HTTP_400_BAD_REQUEST)

        asked = user.requested_role.role_name if user.requested_role else "none stated"
        user.role = role
        user.status = User.ACTIVE
        user.save(update_fields=["role", "status", "updated_at"])
        # Both roles in the audit line: when someone asked for more than they
        # were given, that should be legible a year later.
        log_activity(
            request.user, ActivityLog.UPDATED, ActivityLog.USER,
            entity_type="User",
            entity_label=(f"{user.fullname or user.email} — access approved as "
                          f"{role.role_name} (asked for: {asked})"),
            entity_id=user.id)
        return Response(UserSerializer(user).data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"])
    def decline(self, request, pk=None):
        """Refuse a pending sign-up.

        Archives rather than deletes: an archived address cannot re-register
        itself (accounts/google_auth.py), so a declined applicant cannot simply
        sign in again for a fresh request and wait for a distracted approval.
        Deleting the row would hand them exactly that loop.
        """
        user = self.get_object()
        if user.status != User.PENDING:
            return Response({"detail": "This account is not awaiting approval."},
                            status=status.HTTP_400_BAD_REQUEST)
        asked = user.requested_role.role_name if user.requested_role else "none stated"
        user.status = User.ARCHIVED
        user.save(update_fields=["status", "updated_at"])
        log_activity(
            request.user, ActivityLog.ARCHIVED, ActivityLog.USER,
            entity_type="User",
            entity_label=(f"{user.fullname or user.email} — access request "
                          f"declined (asked for: {asked})"),
            entity_id=user.id)
        return Response({"status": user.status}, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"], url_path="reset-password")
    def reset_password(self, request, pk=None):
        """Admin-issued temporary password. Never accepts a password from the
        request — always generated server-side and returned exactly once."""
        user = self.get_object()
        # Deliberately "not ACTIVE" rather than "is ARCHIVED": a pending
        # account has no role yet, and issuing it a password would hand out a
        # working credential before anyone approved the person.
        if user.status != User.ACTIVE:
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
