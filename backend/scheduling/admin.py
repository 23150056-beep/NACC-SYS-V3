from django.contrib import admin
from scheduling.models import AvailabilityBlock, Appointment

for m in (AvailabilityBlock, Appointment):
    admin.site.register(m)
