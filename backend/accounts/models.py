from django.contrib.auth.models import AbstractUser
from django.db import models

from accounts.managers import UserManager


class Role(models.Model):
    ADMINISTRATOR = "Administrator"
    PSYCHOLOGIST = "Psychologist"
    STAFF = "Staff"

    role_name = models.CharField(max_length=50, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "tbl_role"

    def __str__(self):
        return self.role_name


class User(AbstractUser):
    ACTIVE = "active"
    # Signed up through Google but not yet approved by an administrator. Holds
    # no role and reaches nothing: the account exists only so a human has
    # something to approve.
    PENDING = "pending"
    ARCHIVED = "archived"
    STATUS_CHOICES = [
        (ACTIVE, "Active"), (PENDING, "Pending approval"), (ARCHIVED, "Archived"),
    ]

    email = models.EmailField(unique=True)
    middle_initial = models.CharField(max_length=5, blank=True)
    contact_details = models.CharField(max_length=50, blank=True)
    role = models.ForeignKey(
        Role, on_delete=models.PROTECT, null=True, blank=True, related_name="users"
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=ACTIVE)
    # Set whenever an admin issues a temporary password. Server-side
    # enforcement (see accounts/authentication.py) blocks all other API
    # access until the user sets their own password.
    must_change_password = models.BooleanField(default=False)
    # Single-admin handover: set when this user is created as the successor
    # Administrator while another admin is still active. Their FIRST login
    # archives every other admin account and clears the flag (see
    # accounts/serializers.py LoginSerializer).
    admin_takeover_pending = models.BooleanField(default=False)
    # Google's stable subject identifier, stored the first time this account
    # signs in with Google. Matching on `sub` rather than email from then on
    # means a Google-side email change cannot hand someone else's session to
    # this account, and cannot lock this user out of their own.
    google_sub = models.CharField(
        max_length=255, unique=True, null=True, blank=True, editable=False)
    # What the person said about themselves when they signed up with Google.
    # A CLAIM, never a grant. Nothing in the permission system may read this
    # field — only the approval endpoint does, and only to pre-fill the
    # administrator's choice. `role` stays null until a human decides.
    requested_role = models.ForeignKey(
        Role, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="access_requests", editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["username"]

    objects = UserManager()

    class Meta:
        db_table = "tbl_user"

    def save(self, *args, **kwargs):
        """`status` is the domain truth; `is_active` is what actually gates
        authentication (Django's ModelBackend and SimpleJWT both check it, and
        neither has heard of `status`). Deriving one from the other here means
        the two cannot drift, and — the reason it exists — a status added
        later cannot accidentally authenticate because someone forgot to set
        `is_active` alongside it. Callers set `status` and nothing else.

        Caveat for future work: a queryset-level `.update(status=...)` skips
        this and would leave the two out of step. Change status through an
        instance save."""
        self.is_active = self.status == self.ACTIVE
        update_fields = kwargs.get("update_fields")
        if update_fields is not None:
            update_fields = set(update_fields)
            if "status" in update_fields:
                kwargs["update_fields"] = update_fields | {"is_active"}
        super().save(*args, **kwargs)

    @property
    def fullname(self):
        parts = [self.first_name, self.middle_initial, self.last_name]
        return " ".join(p for p in parts if p)

    def __str__(self):
        return self.email
