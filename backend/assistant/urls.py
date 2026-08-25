from django.urls import path

from assistant.views import (
    AssistantJobFeedbackView, AssistantSettingView, RemarkPolishView,
)

urlpatterns = [
    path("assistant/settings/", AssistantSettingView.as_view(),
         name="assistant-settings"),
    path("assistant/polish-remark/", RemarkPolishView.as_view(),
         name="assistant-polish-remark"),
    path("assistant/jobs/<int:job_id>/feedback/",
         AssistantJobFeedbackView.as_view(), name="assistant-job-feedback"),
]
