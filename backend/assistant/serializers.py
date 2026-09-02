from rest_framework import serializers

from assistant.models import AssistantSetting


class AssistantSettingSerializer(serializers.ModelSerializer):
    class Meta:
        model = AssistantSetting
        fields = ["enabled", "ollama_url", "model_name", "updated_at"]
        read_only_fields = ["updated_at"]

