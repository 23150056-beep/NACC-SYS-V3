from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from accounts.models import Role
from activity.models import ActivityLog
from activity.services import log_activity

User = get_user_model()


class RoleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Role
        fields = ["id", "role_name"]


class UserSerializer(serializers.ModelSerializer):
    role_name = serializers.CharField(source="role.role_name", read_only=True)
    fullname = serializers.CharField(read_only=True)
    # Whether this account signs in with Google. Exposed as a boolean rather
    # than the subject id itself: the directory needs to show *how* someone
    # gets in, and the raw identifier is of no use to any client.
    google_linked = serializers.SerializerMethodField()
    # What the person claimed about themselves at sign-up. Exposed so the
    # approval queue can pre-fill the administrator's choice — and named
    # `requested_` throughout so no client mistakes it for a granted role.
    requested_role_name = serializers.CharField(
        source="requested_role.role_name", read_only=True, default=None)

    class Meta:
        model = User
        fields = [
            "id", "email", "username", "first_name", "last_name",
            "middle_initial", "contact_details", "role", "role_name",
            "requested_role", "requested_role_name",
            "fullname", "status", "must_change_password", "admin_takeover_pending",
            "google_linked", "last_login", "created_at",
        ]
        read_only_fields = [
            "must_change_password", "admin_takeover_pending",
            "requested_role", "requested_role_name",
            "google_linked", "last_login", "created_at",
        ]

    def get_google_linked(self, obj):
        return bool(obj.google_sub)


class UserWriteSerializer(serializers.ModelSerializer):
    """Passwords are deliberately NOT accepted here — admins never choose
    another user's password. Creation issues a server-generated temporary
    password (see UserViewSet.create); later changes go through the
    reset-password action or the user's own change-password endpoint."""
    # Email IS the username — the field is optional and derived from email.
    username = serializers.CharField(required=False, allow_blank=True)
    role = serializers.PrimaryKeyRelatedField(
        queryset=Role.objects.all(), required=False, allow_null=True)

    class Meta:
        model = User
        fields = [
            "id", "email", "username", "first_name", "last_name",
            "middle_initial", "contact_details", "role", "status",
        ]

    def validate(self, attrs):
        """An account may not be saved into the roleless state.

        The column stays nullable because a pending Google sign-up genuinely has
        no role until someone approves it. But a roleless *active* account has
        no defined access and is refused at authentication, so saving one would
        only produce a colleague who cannot sign in and no explanation why.

        Two directions, one rule: an administrator creating an account by hand
        must choose a role, and an existing role cannot be emptied back to none.
        Removing someone's access is what deactivation is for — it says so on
        the screen, and it is reversible.

        Ordinary edits that leave `role` out of the payload are untouched: only
        a present-and-empty value is a removal.
        """
        if self.instance is None:
            if not attrs.get("role"):
                raise serializers.ValidationError(
                    {"role": "Choose a role — an account without one cannot sign in."})
        elif "role" in attrs and not attrs["role"] and self.instance.role_id:
            raise serializers.ValidationError(
                {"role": "Removing the role would lock this account out. "
                         "Deactivate the account instead."})
        return attrs

    def create(self, validated_data):
        if not validated_data.get("username"):
            validated_data["username"] = validated_data.get("email")
        user = User(**validated_data)
        # The view sets the real temp password right after; the unusable
        # placeholder guarantees no login window exists before it does.
        user.set_unusable_password()
        user.save()
        return user

    def validate_role(self, value):
        """A role can be corrected, but not in the two directions that would
        break something the rest of the system depends on.

        Roles used to be frozen once assigned (adviser's rule). That left an
        administrator who picked the wrong one with no way back except
        deactivating the person and creating them again, which loses their
        history. Changing one is allowed now — with these two exceptions,
        which are not preferences:

        * Nobody can be promoted INTO Administrator here. Creating an
          administrator triggers the single-admin handover (every other admin
          is archived at their first sign-in, see _complete_admin_takeover);
          reaching that state through an edit would skip the flow entirely and
          leave two live administrators, which the design does not allow.
        * An Administrator's role cannot be changed away. It is the agency's
          recovery account, and there may be only one.
        """
        instance = self.instance
        if instance is None or instance.role_id == getattr(value, "id", None):
            return value
        if value and value.role_name == Role.ADMINISTRATOR:
            raise serializers.ValidationError(
                "An account cannot be changed into an Administrator. Add a new "
                "administrator account instead — that path hands over properly.")
        if instance.role and instance.role.role_name == Role.ADMINISTRATOR:
            raise serializers.ValidationError(
                "An Administrator's role cannot be changed. Create the "
                "replacement administrator first.")
        return value

    def update(self, instance, validated_data):
        previous_role = instance.role
        new_role = validated_data.get("role", previous_role)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        # Keep username in sync with email (email is the username).
        if validated_data.get("email"):
            instance.username = validated_data["email"]
        instance.save()

        # Logged separately from the ordinary "updated" line, and naming both
        # roles: "who made her a psychologist, and when" is a question the
        # audit trail has to answer on its own.
        if new_role != previous_role:
            actor = self.context["request"].user
            log_activity(
                actor, ActivityLog.UPDATED, ActivityLog.USER,
                entity_type="User",
                entity_label=(f"{instance.fullname or instance.email} — role changed "
                              f"from {previous_role.role_name if previous_role else 'none'} "
                              f"to {new_role.role_name if new_role else 'none'}"),
                entity_id=instance.id)
        return instance


class ChangePasswordSerializer(serializers.Serializer):
    """Voluntary or forced (must_change_password) self-service password change.
    The requesting user always comes from the view via context — never from
    the request body — so this can't be used to change someone else's password."""
    current_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True)

    def validate_current_password(self, value):
        user = self.context["request"].user
        if not user.check_password(value):
            raise serializers.ValidationError("Current password is incorrect.")
        return value

    def validate(self, attrs):
        user = self.context["request"].user
        if attrs["new_password"] == attrs["current_password"]:
            raise serializers.ValidationError(
                {"new_password": "New password must be different from the current password."})
        try:
            validate_password(attrs["new_password"], user)
        except DjangoValidationError as exc:
            raise serializers.ValidationError({"new_password": exc.messages})
        return attrs

    def save(self):
        user = self.context["request"].user
        user.set_password(self.validated_data["new_password"])
        user.must_change_password = False
        user.save(update_fields=["password", "must_change_password", "updated_at"])
        return user


def _complete_admin_takeover(new_admin):
    """The successor administrator's first login: archive every other admin
    account (their sessions die immediately — archived users fail JWT auth)
    and clear the pending flag. A deactivated admin can only return via a
    brand-new account (product decision 2026-07-18)."""
    others = (User.objects
              .filter(role__role_name=Role.ADMINISTRATOR, status=User.ACTIVE)
              .exclude(pk=new_admin.pk))
    for old in others:
        old.status = User.ARCHIVED
        # is_active follows status automatically (User.save).
        old.save(update_fields=["status", "updated_at"])
        log_activity(
            new_admin, ActivityLog.ARCHIVED, ActivityLog.USER,
            entity_type="User",
            entity_label=f"{old.fullname or old.email} (admin handover)",
            entity_id=old.id)
    new_admin.admin_takeover_pending = False
    new_admin.save(update_fields=["admin_takeover_pending", "updated_at"])


class LoginSerializer(TokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token["role"] = user.role.role_name if user.role else None
        return token

    def validate(self, attrs):
        data = super().validate(attrs)
        # Runs before the user payload is built so the response reflects the
        # cleared flag and the old admin is locked out before this response
        # even lands.
        if self.user.admin_takeover_pending:
            _complete_admin_takeover(self.user)
        data["user"] = UserSerializer(self.user).data
        log_activity(self.user, ActivityLog.LOGIN, ActivityLog.SECURITY)
        return data
