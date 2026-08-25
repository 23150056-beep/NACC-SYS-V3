from django.urls import path

from assistant.views import AssistantSettingView, RemarkPolishView

urlpatterns = [
    path("assistant/settings/", AssistantSettingView.as_view(),
         name="assistant-settings"),
    path("assistant/polish-remark/", RemarkPolishView.as_view(),
         name="assistant-polish-remark"),
]
