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
    ARCHIVED = "archived"
    STATUS_CHOICES = [(ACTIVE, "Active"), (ARCHIVED, "Archived")]

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
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["username"]

    objects = UserManager()

    class Meta:
        db_table = "tbl_user"

    @property
    def fullname(self):
        parts = [self.first_name, self.middle_initial, self.last_name]
        return " ".join(p for p in parts if p)

    def __str__(self):
        return self.email
