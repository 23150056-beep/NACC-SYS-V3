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

    class Meta:
        model = User
        fields = [
            "id", "email", "username", "first_name", "last_name",
            "middle_initial", "contact_details", "role", "role_name",
            "fullname", "status", "must_change_password", "admin_takeover_pending",
        ]
        read_only_fields = ["must_change_password", "admin_takeover_pending"]


class UserWriteSerializer(serializers.ModelSerializer):
    """Passwords are deliberately NOT accepted here — admins never choose
    another user's password. Creation issues a server-generated temporary
    password (see UserViewSet.create); later changes go through the
    reset-password action or the user's own change-password endpoint."""
    # Email IS the username — the field is optional and derived from email.
    username = serializers.CharField(required=False, allow_blank=True)

    class Meta:
        model = User
        fields = [
            "id", "email", "username", "first_name", "last_name",
            "middle_initial", "contact_details", "role", "status",
        ]

    def create(self, validated_data):
        if not validated_data.get("username"):
            validated_data["username"] = validated_data.get("email")
        user = User(**validated_data)
        # The view sets the real temp password right after; the unusable
        # placeholder guarantees no login window exists before it does.
        user.set_unusable_password()
        user.save()
        return user

    def update(self, instance, validated_data):
        # A role cannot be changed once it has been assigned (adviser).
        if instance.role_id is not None:
            validated_data.pop("role", None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        # Keep username in sync with email (email is the username).
        if validated_data.get("email"):
            instance.username = validated_data["email"]
        instance.save()
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
        old.is_active = False
        old.save(update_fields=["status", "is_active", "updated_at"])
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
