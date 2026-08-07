from django.urls import path
from rest_framework.routers import DefaultRouter
from clinical.views import (
    InstrumentCatalogViewSet, AgencyFormTemplateViewSet,
    ConsentRecordViewSet, ClinicalInterviewRecordViewSet, ProblemEntryViewSet,
    PreAssessmentViewSet, PsychologicalReportViewSet, RemarkNoteViewSet,
    TreatmentPlanViewSet, ResultEntryViewSet, CaseReferralViewSet,
    OpinionnaireInviteViewSet, PublicOpinionnaireView,
)
from clinical.reports_views import (
    ChildReportView, MonitoringListView, SummaryReportView, DashboardView,
)

router = DefaultRouter()
router.register("instruments", InstrumentCatalogViewSet, basename="instrument")
router.register("form-templates", AgencyFormTemplateViewSet, basename="form-template")
router.register("consents", ConsentRecordViewSet, basename="consent")
router.register("interviews", ClinicalInterviewRecordViewSet, basename="interview")
router.register("problems", ProblemEntryViewSet, basename="problem")
router.register("pre-assessments", PreAssessmentViewSet, basename="pre-assessment")
router.register("report-files", PsychologicalReportViewSet, basename="report-file")
router.register("remarks", RemarkNoteViewSet, basename="remark")
router.register("treatment-plans", TreatmentPlanViewSet, basename="treatment-plan")
router.register("result-entries", ResultEntryViewSet, basename="result-entry")
router.register("case-referrals", CaseReferralViewSet, basename="case-referral")
router.register("opinionnaire-invites", OpinionnaireInviteViewSet, basename="opinionnaire-invite")
router.register("opinionnaire", PublicOpinionnaireView, basename="opinionnaire-public")

urlpatterns = router.urls + [
    path("reports/child/<int:child_id>/", ChildReportView.as_view(), name="report-child"),
    path("reports/summary/", SummaryReportView.as_view(), name="report-summary"),
    path("reports/dashboard/", DashboardView.as_view(), name="report-dashboard"),
    path("reports/monitoring/", MonitoringListView.as_view(), name="report-monitoring"),
]
