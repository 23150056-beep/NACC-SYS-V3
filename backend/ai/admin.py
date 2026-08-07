from django.contrib import admin
from ai.models import AISetting, AIJob

for m in (AISetting, AIJob):
    admin.site.register(m)
