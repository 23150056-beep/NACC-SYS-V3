from django.urls import path

from assistant.views import (
    AssistantJobFeedbackView, AssistantSettingView, CensusNarrativeView,
    ConfirmSummaryView, DocumentSummaryView, LatestBriefView,
    PreSessionBriefView, PrefetchBriefsView, RemarkPolishView,
)

urlpatterns = [
    path("assistant/settings/", AssistantSettingView.as_view(),
         name="assistant-settings"),
    path("assistant/polish-remark/", RemarkPolishView.as_view(),
         name="assistant-polish-remark"),
    path("assistant/jobs/<int:job_id>/feedback/",
         AssistantJobFeedbackView.as_view(), name="assistant-job-feedback"),
    path("assistant/brief/child/<int:child_id>/", PreSessionBriefView.as_view(),
         name="assistant-brief"),
    path("assistant/brief/child/<int:child_id>/latest/", LatestBriefView.as_view(),
         name="assistant-brief-latest"),
    path("assistant/prefetch-briefs/", PrefetchBriefsView.as_view(),
         name="assistant-prefetch-briefs"),
    path("assistant/summarize-report/<int:doc_id>/",
         DocumentSummaryView.as_view(kind="report"),
         name="assistant-summarize-report"),
    path("assistant/summarize-case-referral/<int:doc_id>/",
         DocumentSummaryView.as_view(kind="case-referral"),
         name="assistant-summarize-case-referral"),
    path("assistant/confirm-summary/<int:doc_id>/",
         ConfirmSummaryView.as_view(kind="report"),
         name="assistant-confirm-summary"),
    path("assistant/confirm-case-referral-summary/<int:doc_id>/",
         ConfirmSummaryView.as_view(kind="case-referral"),
         name="assistant-confirm-case-referral-summary"),
    path("assistant/census-narrative/", CensusNarrativeView.as_view(),
         name="assistant-census-narrative"),
]
