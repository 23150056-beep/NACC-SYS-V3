from django.contrib import admin
from clinical.models import (
    InstrumentCatalog, AgencyFormTemplate, ConsentRecord,
    ClinicalInterviewRecord, ProblemEntry,
)

for m in (InstrumentCatalog, AgencyFormTemplate, ConsentRecord,
          ClinicalInterviewRecord, ProblemEntry):
    admin.site.register(m)
