from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from accounts.models import Role, User

admin.site.register(Role)
admin.site.register(User, UserAdmin)
