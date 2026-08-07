from django.urls import path
from ai.views import (
    AISettingView, PreSessionBriefView, ReportSummaryDraftView,
    ConfirmReportSummaryView, RemarkPolishView, CensusNarrativeView,
    LatestBriefView, PrefetchBriefsView,
    CaseReferralSummaryDraftView, ConfirmCaseReferralSummaryView,
    AIJobFeedbackView, AIMetricsView,
)

urlpatterns = [
    path("ai/settings/", AISettingView.as_view(), name="ai-settings"),
    path("ai/brief/child/<int:child_id>/", PreSessionBriefView.as_view(), name="ai-brief"),
    path("ai/brief/child/<int:child_id>/latest/", LatestBriefView.as_view(), name="ai-brief-latest"),
    path("ai/prefetch-briefs/", PrefetchBriefsView.as_view(), name="ai-prefetch-briefs"),
    path("ai/summarize-report/<int:report_id>/", ReportSummaryDraftView.as_view(), name="ai-summarize-report"),
    path("ai/confirm-summary/<int:report_id>/", ConfirmReportSummaryView.as_view(), name="ai-confirm-summary"),
    path("ai/summarize-case-referral/<int:case_referral_id>/", CaseReferralSummaryDraftView.as_view(), name="ai-summarize-case-referral"),
    path("ai/confirm-case-referral-summary/<int:case_referral_id>/", ConfirmCaseReferralSummaryView.as_view(), name="ai-confirm-case-referral-summary"),
    path("ai/polish-remark/", RemarkPolishView.as_view(), name="ai-polish-remark"),
    path("ai/census-narrative/", CensusNarrativeView.as_view(), name="ai-census-narrative"),
    path("ai/jobs/<int:job_id>/feedback/", AIJobFeedbackView.as_view(), name="ai-job-feedback"),
    path("ai/metrics/", AIMetricsView.as_view(), name="ai-metrics"),
]
