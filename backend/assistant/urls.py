from django.urls import path

from assistant.views import AssistantSettingView

urlpatterns = [
    path("assistant/settings/", AssistantSettingView.as_view(),
         name="assistant-settings"),
]
